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
        # In questi test i dati CSV sono gia' stati verificati dall'utente
        # fittizio: non si omette la conferma dei candidati multivariati.
        "significatoEstremi": "reali",
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
assert matrice_presenze["matrice"][0][1] == 0
assert matrice_presenze["matrice"][0][2] == 1
verifica_matrice_finale(p.calcola_matrice(
    solo_presenze,
    {"riga": "evento", "zeriCondivisi": "no", "colonne": {}},
), 3)

dati_misti_estremi = p.prepara_tabella(
    p.leggi_csv("a,categoria\n10,x\n12,y\n11,x\n9,z\n13,y\n10,x\n12,z\n80,y")
)
matrice_classica_default = p.calcola_matrice_gower(
    dati_misti_estremi,
    {"riga": "oggetto", "significatoEstremi": "reali", "colonne": {}},
)
assert matrice_classica_default["metodo"] == "Dissimilarità di Gower classica"
risposte_robuste = {
    "riga": "oggetto", "significatoEstremi": "reali", "colonne": {},
    "tipoGowerNumeriche": "robusta", "righeOutlierGower": {"a": "8"},
}
matrice_robusta = p.calcola_matrice_gower(dati_misti_estremi, risposte_robuste)
assert matrice_robusta["metodo"] == "Dissimilarità di Gower robusta"
assert matrice_robusta["matrice"][0][1] > matrice_classica_default["matrice"][0][1]
quasi_uguali(matrice_robusta["matrice"][0][1], .75)
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
    "ordiniTemporaliGruppi": {"gruppo-1": "a; b"},
    "campionamentiTemporaliGruppi": {"gruppo-1": "regolare"},
    "confermeValoriOriginaliGruppi": {"gruppo-1": "si"},
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
    "ordiniTemporaliGruppi": {"tempo": "t0; t1; t2"},
    "campionamentiTemporaliGruppi": {"tempo": "regolare"},
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
matrice_tempo_interpolata = p._calcola_matrice_specializzata(
    dati_tempo_mancanti, risposte_tempo_interpolate,
    piano_tempo_interpolato["percorsi"][0],
)
assert matrice_tempo_interpolata["matrice"][0][1] is not None
assert matrice_tempo_interpolata["matrice"][0][3] is None
assert "interpolati linearmente" in matrice_tempo_interpolata["nota"]
try:
    p.calcola_matrice(dati_tempo_mancanti, risposte_tempo_interpolate)
    assert False, "La matrice incompleta deve bloccare il risultato finale."
except ValueError as errore:
    assert "coppie non hanno alcun contributo valido" in str(errore)

risposte_tempo_esclusione = {
    **risposte_tempo_mancanti,
    "mancanti-gruppo-tempo": "escludi_percorso",
}
piano_tempo_esclusione = p.crea_piano_confronto(
    dati_tempo_mancanti, risposte_tempo_esclusione
)
matrice_tempo_esclusione = p._calcola_matrice_specializzata(
    dati_tempo_mancanti, risposte_tempo_esclusione,
    piano_tempo_esclusione["percorsi"][0],
)
assert matrice_tempo_esclusione["matrice"][1][2] is not None
assert matrice_tempo_esclusione["matrice"][0][1] is None
try:
    p.calcola_matrice(dati_tempo_mancanti, risposte_tempo_esclusione)
    assert False, "La matrice incompleta deve bloccare il risultato finale."
except ValueError as errore:
    assert "coppie non hanno alcun contributo valido" in str(errore)

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
risposte_testo_esclusione = {
    **risposte_testo_mancante,
    "mancantiSpecializzatiPerColonna": {"testo": "escludi_percorso"},
}
piano_testo_esclusione = p.crea_piano_confronto(
    dati_testo_mancante, risposte_testo_esclusione
)
matrice_testo_esclusione = p._calcola_matrice_specializzata(
    dati_testo_mancante, risposte_testo_esclusione,
    piano_testo_esclusione["percorsi"][0],
)
assert matrice_testo_esclusione["matrice"][0][1] is None
try:
    p.calcola_matrice(dati_testo_mancante, risposte_testo_esclusione)
    assert False, "La matrice incompleta deve bloccare il risultato finale."
except ValueError as errore:
    assert "coppie non hanno alcun contributo valido" in str(errore)
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
piano_misto_robusto_senza_scalatura = p.crea_piano_confronto(
    misti_con_due_quantita, {**base_misto_due, "tipoGowerNumeriche": "robusta"}
)
assert not piano_misto_robusto_senza_scalatura["completo"]
assert "righe anomale" in " ".join(piano_misto_robusto_senza_scalatura["percorsi"][0]["avvisi"])
piano_misto_robusto = p.crea_piano_confronto(
    misti_con_due_quantita,
    {**base_misto_due, "tipoGowerNumeriche": "robusta", "righeOutlierGower": {"b": "4"}},
)
assert piano_misto_classico["percorsi"][0]["metodo"] == "Dissimilarità di Gower classica"
assert piano_misto_robusto["percorsi"][0]["metodo"] == "Dissimilarità di Gower robusta"
assert piano_misto_robusto["percorsi"][0]["calcolo"]["disponibile"] is True
assert not p.crea_piano_confronto(
    misti_con_due_quantita,
    {**base_misto_due, "tipoGowerNumeriche": "robusta", "righeOutlierGower": {"b": "0"}},
)["completo"]


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

# Le colonne costanti conservano il proprio peso nel denominatore (decisione 7).
dati_costanti, piano_costanti, risposte_costanti = piano_gower_per(
    "classe,costante\nrosso,5\nblu,5\nrosso,5",
    colonne={"classe": {"ruolo": "categoria", "usa": True},
             "costante": {"ruolo": "quantita", "usa": True}},
)
assert piano_costanti["completo"], piano_costanti
assert piano_costanti["percorsi"][0]["colonneCostantiGower"] == ["costante"]
assert piano_costanti["percorsi"][0]["pesiGower"] == {"classe": 1.0, "costante": 1.0}
quasi_uguali(p.calcola_matrice_gower(dati_costanti, risposte_costanti)["matrice"][0][1], .5)
tutti_costanti, piano_tutti_costanti, _ = piano_gower_per(
    "classe,costante\nrosso,5\nrosso,5\nrosso,5",
    colonne={"classe": {"ruolo": "categoria", "usa": True},
             "costante": {"ruolo": "quantita", "usa": True}},
)
assert piano_tutti_costanti["completo"], piano_tutti_costanti
assert piano_tutti_costanti["percorsi"][0]["colonneCostantiGower"] == ["classe", "costante"]
assert all(valore == 0 for riga in p.calcola_matrice_gower(tutti_costanti, {
    "riga": "oggetto", "colonne": {
        "classe": {"ruolo": "categoria", "usa": True},
        "costante": {"ruolo": "quantita", "usa": True},
    },
})["matrice"] for valore in riga)

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

# Regressioni: decisione 42, DTW a costo medio esatto.
# Il cammino a costo totale minimo non coincide con quello a costo medio minimo.
quasi_uguali(p._distanza_dtw([0, 0, 0], [1, 1, 2]), 1.2)
quasi_uguali(p._distanza_dtw([1, 2, 3], [1, 2, 3]), 0.0)
try:
    p._distanza_dtw([], [1])
    assert False, "Una serie vuota deve essere rifiutata."
except ValueError:
    pass

# Regressione: massimo campionario anziche' 95-esimo percentile.
normalizzata, criterio = p._normalizza_per_aggregazione({
    "matrice": [[0, 1, 4], [1, 0, 2], [4, 2, 0]],
    "limiteAggregazione": None,
})
quasi_uguali(normalizzata[0][1], .25)
quasi_uguali(normalizzata[0][2], 1.0)
assert "massimo campionario" in criterio

# Anche con un solo percorso, il risultato finale del sito appartiene a [0,1].
matrice_singolo_finale = p.calcola_matrice(scale_diverse, risposte_accessibili)
assert all(
    valore is None or 0 <= valore <= 1
    for riga in matrice_singolo_finale["matrice"] for valore in riga
)
assert "Normalizzazione finale" in matrice_singolo_finale["nota"]

# Le anomalie diagnostiche non impediscono il calcolo; gli errori si' (decisione 45).
diagnostica_zero = p._valida_matrice_finale(
    [[0, 0], [0, 0]], ["A", "B"]
)
assert diagnostica_zero["coppieZeroDistinte"] == 1
assert diagnostica_zero["avvisi"]
for matrice_errata in (
    [[0, None], [None, 0]],
    [[0, float("nan")], [float("nan"), 0]],
    [[0, .5], [.4, 0]],
    [[0, 1.1], [1.1, 0]],
):
    try:
        p._valida_matrice_finale(matrice_errata, ["A", "B"])
        assert False, "Il validatore deve bloccare matrici non valide."
    except ValueError:
        pass

# Integrazione a tre blocchi: una sola tabella numerica, tre confronti indipendenti.
# Il gruppo temporale usa DTW, il profilo Pearson e le coordinate Minkowski
# pesata. Nessuna colonna puo' contribuire due volte.
csv_blocchi_eterogenei = (
    "t1,t2,t3,p1,p2,p3,c1,c2\n"
    "1,3,4,1,3,2,5,8\n"
    "2,4,5,2,6,4,7,4\n"
    "1,4,3,4,1,3,2,10\n"
    "3,2,1,5,4,3,9,3\n"
    "2,2,3,3,1,4,4,6\n"
)
dati_blocchi_eterogenei = p.prepara_tabella(p.leggi_csv(csv_blocchi_eterogenei))
risposte_blocchi_eterogenei = {
    "riga": "oggetto",
    "significatoEstremi": "reali",
    "riscalamentoConfermato": True,
    "confrontoQuantitativo": "assoluto",
    "gestioneDipendenzaLineare": "mantieni",
    "colonne": {
        nome: {"ruolo": "quantita", "usa": True}
        for nome in ("t1", "t2", "t3", "p1", "p2", "p3", "c1", "c2")
    },
    "gruppi": [
        {"id": "tempo", "nome": "Serie temporale", "tipo": "tempo"},
        {"id": "profilo", "nome": "Profilo", "tipo": "ripetute"},
        {"id": "coordinate", "nome": "Coordinate", "tipo": "coordinate"},
    ],
    "assegnazioni": {
        **{nome: "tempo" for nome in ("t1", "t2", "t3")},
        **{nome: "profilo" for nome in ("p1", "p2", "p3")},
        **{nome: "coordinate" for nome in ("c1", "c2")},
    },
    "ritardo-tempo": "si",
    "ordiniTemporaliGruppi": {"tempo": "t1; t2; t3"},
    "campionamentiTemporaliGruppi": {"tempo": "regolare"},
    "somiglianza-profilo": "andamento",
    "confermeValoriOriginaliGruppi": {"tempo": "si", "profilo": "si"},
    "misureGruppi": {"coordinate": "weighted_minkowski"},
    "ordiniGruppi": {"coordinate": "3"},
    "pesiGruppi": {"coordinate": "1; 2"},
}
piano_eterogeneo = p.crea_piano_confronto(
    dati_blocchi_eterogenei, risposte_blocchi_eterogenei
)
assert piano_eterogeneo["completo"], piano_eterogeneo
assert piano_eterogeneo["conteggioPercorsi"] == 3
assert all(v["calcolo"]["disponibile"] for v in piano_eterogeneo["percorsi"])
assert [v["metodo"] for v in piano_eterogeneo["percorsi"]] == [
    "Dynamic Time Warping", "Dissimilarità di Pearson", "Distanza di Minkowski pesata"
]
assert [v["colonne"] for v in piano_eterogeneo["percorsi"]] == [
    ["t1", "t2", "t3"], ["p1", "p2", "p3"], ["c1", "c2"]
]
assert piano_eterogeneo["percorsi"][2]["parametri"] == {"q": 3.0, "pesi": [1.0, 2.0]}
assert piano_eterogeneo["percorsi"][2]["preelaborazione"]["usaTabellaTrasformata"]
assert not piano_eterogeneo["percorsi"][1]["preelaborazione"]["usaTabellaTrasformata"]
assert not piano_eterogeneo["percorsi"][0]["preelaborazione"]["usaTabellaTrasformata"]
finale_eterogeneo = p.calcola_matrice(
    dati_blocchi_eterogenei, risposte_blocchi_eterogenei
)
verifica_matrice_finale(finale_eterogeneo, 5)
assert finale_eterogeneo["metodo"] == "Dissimilarità complessiva pesata"
assert len(finale_eterogeneo["contributi"]) == 3
assert all(
    valore is not None and 0 <= valore <= 1
    for riga in finale_eterogeneo["matrice"] for valore in riga
)
assert finale_eterogeneo["diagnosticaFinale"]["coppieTotali"] == 10

# Un controllo quantitativo dell'aggregazione, non soltanto di dimensioni e nomi.
locali_eterogenei = [
    p._normalizza_per_aggregazione(
        p._calcola_matrice_specializzata(
            dati_blocchi_eterogenei, risposte_blocchi_eterogenei, percorso
        )
    )[0]
    for percorso in piano_eterogeneo["percorsi"]
]
for i in range(5):
    for j in range(i + 1, 5):
        valore_atteso = sum(m[i][j] for m in locali_eterogenei) / 3
        quasi_uguali(finale_eterogeneo["matrice"][i][j], valore_atteso)

# Variare la misura o i pesi di un blocco non deve sovrascrivere gli altri.
risposte_q_uno = {
    **risposte_blocchi_eterogenei, "ordiniGruppi": {"coordinate": "1"}
}
piano_q_uno = p.crea_piano_confronto(dati_blocchi_eterogenei, risposte_q_uno)
assert piano_q_uno["completo"]
assert piano_q_uno["percorsi"][0]["metodo"] == "Dynamic Time Warping"
assert piano_q_uno["percorsi"][1]["metodo"] == "Dissimilarità di Pearson"
assert piano_q_uno["percorsi"][2]["parametri"]["q"] == 1
assert p.calcola_matrice(
    dati_blocchi_eterogenei, risposte_q_uno
)["matrice"] != finale_eterogeneo["matrice"]

risposte_peso_gruppo = {
    **risposte_blocchi_eterogenei,
    "pesiPercorsi": {"percorso-1": "4", "percorso-2": "1", "percorso-3": "1"},
}
finale_peso_gruppo = p.calcola_matrice(
    dati_blocchi_eterogenei, risposte_peso_gruppo
)
assert finale_peso_gruppo["matrice"] != finale_eterogeneo["matrice"]
assert [v["peso"] for v in finale_peso_gruppo["contributi"]] == [4, 1, 1]

for configurazione in (
    {"misureGruppi": {}},  # coordinate quantitative senza misura confermata
    {"ordiniGruppi": {"coordinate": "0.5"}},
    {"pesiGruppi": {"coordinate": "1; 0"}},
    {"pesiGruppi": {"coordinate": "1"}},
):
    invalidi = {**risposte_blocchi_eterogenei, **configurazione}
    assert not p.crea_piano_confronto(
        dati_blocchi_eterogenei, invalidi
    )["completo"], configurazione

# La stessa tabella funziona anche con coordinate numeriche INDIPENDENTI.
# La scelta globale di Minkowski non modifica DTW e Pearson.
risposte_coordinate_indipendenti = {
    **risposte_blocchi_eterogenei,
    "gruppi": risposte_blocchi_eterogenei["gruppi"][:2],
    "assegnazioni": {
        k: v for k, v in risposte_blocchi_eterogenei["assegnazioni"].items()
        if v != "coordinate"
    },
    "misuraNumericaManuale": "minkowski",
    "ordineMisuraManuale": "3",
    "dipendenzaCoordinate": "no",
    "aggregazioneScarti": "quadratica",
    "importanzaCoordinate": "uguale",
}
piano_indipendenti = p.crea_piano_confronto(
    dati_blocchi_eterogenei, risposte_coordinate_indipendenti
)
assert piano_indipendenti["completo"], piano_indipendenti
assert piano_indipendenti["conteggioPercorsi"] == 3
assert [v["metodo"] for v in piano_indipendenti["percorsi"]] == [
    "Distanza di Minkowski", "Dynamic Time Warping", "Dissimilarità di Pearson"
]
verifica_matrice_finale(
    p.calcola_matrice(dati_blocchi_eterogenei, risposte_coordinate_indipendenti), 5
)


# Proposte guidate: le intestazioni e le correlazioni sono SOLO indizi.
# I suggerimenti non modificano ne' le assegnazioni ne' i percorsi del piano.
nomi_collaudo = ["t1", "t2", "t3", "p1", "p2", "p3", "c1", "c2"]
proposte_collaudo = p._proponi_gruppi_numerici(
    nomi_collaudo, p._diagnosi_numerica(
        nomi_collaudo,
        {colonna["nome"]: colonna for colonna in dati_blocchi_eterogenei["colonne"]},
    )
)
assert [proposta["colonne"] for proposta in proposte_collaudo] == [
    ["t1", "t2", "t3"], ["p1", "p2", "p3"], ["c1", "c2"],
]
assert all(proposta["fonte"] == "intestazioni" for proposta in proposte_collaudo)
assert all("tipo" not in proposta for proposta in proposte_collaudo)
assert len({c for proposta in proposte_collaudo for c in proposta["colonne"]}) == 8
risposta_diagnosi = json.loads(p.analizza_diagnosi_numerica_json(
    csv_blocchi_eterogenei, "[]", json.dumps(nomi_collaudo)
))
assert risposta_diagnosi["ok"]
assert risposta_diagnosi["gruppiSuggeriti"] == proposte_collaudo

# Una correlazione forte e' evidenza statistica, non conferma semantica.
csv_correlato_senza_prefissi = (
    "altezza,peso,colore\n"
    "1,2,4\n2,4,1\n3,6,6\n4,8,2\n5,10,5\n6,12,3\n"
)
dati_correlati = p.prepara_tabella(p.leggi_csv(csv_correlato_senza_prefissi))
nomi_correlati = ["altezza", "peso", "colore"]
proposte_correlate = p._proponi_gruppi_numerici(
    nomi_correlati, p._diagnosi_numerica(
        nomi_correlati, {c["nome"]: c for c in dati_correlati["colonne"]}
    )
)
assert any(
    proposta["colonne"] == ["altezza", "peso"]
    and proposta["fonte"] == "correlazione"
    and "tipo" not in proposta
    for proposta in proposte_correlate
), proposte_correlate

# Due colonne con numeri nell'intestazione ma indici duplicati non sono
# presentate come una sequenza ordinata da usare automaticamente.
assert not p._proponi_gruppi_numerici(
    ["x1", "x_1"], {"relazioniCoppie": []}
)


# Le serie temporali non possono usare implicitamente l'ordine del CSV.
senza_conferma_tempo = {
    **risposte_blocchi_eterogenei,
    "ordiniTemporaliGruppi": {},
}
piano_senza_ordine = p.crea_piano_confronto(
    dati_blocchi_eterogenei, senza_conferma_tempo
)
assert not piano_senza_ordine["completo"]
assert any("ordine cronologico" in avviso for avviso in
           next(percorso for percorso in piano_senza_ordine["percorsi"]
                if percorso["tipoGruppo"] == "tempo")["avvisi"])
for ordine_inesatto in ("t1; t2; t2", "t1; t2", "t1; t2; estranea"):
    piano_invalido = p.crea_piano_confronto(
        dati_blocchi_eterogenei,
        {**risposte_blocchi_eterogenei,
         "ordiniTemporaliGruppi": {"tempo": ordine_inesatto}},
    )
    assert not piano_invalido["completo"], ordine_inesatto
assert not p.crea_piano_confronto(
    dati_blocchi_eterogenei,
    {**risposte_blocchi_eterogenei,
     "campionamentiTemporaliGruppi": {"tempo": "irregolare"}},
)["completo"]
assert not p.crea_piano_confronto(
    dati_blocchi_eterogenei,
    {**risposte_blocchi_eterogenei,
     "campionamentiTemporaliGruppi": {}},
)["completo"]

# Cambiare l'ordine dei tempi modifica davvero i vettori e la DTW locale,
# non soltanto la descrizione del percorso nel piano.
dati_ordine = p.prepara_tabella(p.leggi_csv(
    "t1,t2,t3\n0,10,0\n0,0,10\n10,0,0"
))
base_ordine = {
    "riga": "oggetto",
    "colonne": {nome: {"ruolo": "quantita", "usa": True}
                for nome in ("t1", "t2", "t3")},
    "gruppi": [{"id": "serie", "nome": "Serie", "tipo": "tempo"}],
    "assegnazioni": {nome: "serie" for nome in ("t1", "t2", "t3")},
    "ritardo-serie": "si",
    "campionamentiTemporaliGruppi": {"serie": "regolare"},
    "ordiniTemporaliGruppi": {"serie": "t1; t2; t3"},
}
piano_ordine = p.crea_piano_confronto(dati_ordine, base_ordine)
assert piano_ordine["completo"], piano_ordine
percorso_ordine = piano_ordine["percorsi"][0]
assert percorso_ordine["colonne"] == ["t1", "t2", "t3"]
matrice_ordine = p._calcola_matrice_specializzata(
    dati_ordine, base_ordine, percorso_ordine
)["matrice"]
altra_configurazione = {
    **base_ordine, "ordiniTemporaliGruppi": {"serie": "t2; t1; t3"}
}
piano_altro_ordine = p.crea_piano_confronto(dati_ordine, altra_configurazione)
assert piano_altro_ordine["completo"], piano_altro_ordine
assert piano_altro_ordine["percorsi"][0]["colonne"] == ["t2", "t1", "t3"]
matrice_altro_ordine = p._calcola_matrice_specializzata(
    dati_ordine, altra_configurazione, piano_altro_ordine["percorsi"][0]
)["matrice"]
assert abs(matrice_ordine[0][1] - matrice_altro_ordine[0][1]) > 1e-10


# Confronto numerico pairwise: media pesata sui soli indici osservati
# da entrambi. I mancanti non devono essere trasformati in zeri.
x_pair = [1.0, None, 6.0]
y_pair = [4.0, 3.0, 2.0]
pesi_pair = {"q": 2, "pesi": [1, 2, 3]}
quasi_uguali(
    p._distanza_coordinate_comuni(x_pair, y_pair, "weighted_minkowski", pesi_pair),
    math.sqrt((1 * 3**2 + 3 * 4**2) / 4),
)
quasi_uguali(
    p._distanza_coordinate_comuni(x_pair, y_pair, "euclidean", {}),
    math.sqrt((3**2 + 4**2) / 2),
)
quasi_uguali(
    p._distanza_coordinate_comuni(x_pair, y_pair, "manhattan", {}),
    (3 + 4) / 2,
)
quasi_uguali(
    p._distanza_coordinate_comuni(x_pair, y_pair, "chebyshev", {}),
    4,
)
assert p._distanza_coordinate_comuni(
    [None, 3.0], [4.0, None], "weighted_minkowski", pesi_pair | {"pesi": [1, 2]}
) is None
try:
    p._distanza_coordinate_comuni(x_pair, y_pair, "mahalanobis", {})
    assert False, "Non consentire pairwise con Mahalanobis."
except ValueError:
    pass

# Percorso numerico: nessun nuovo valore imputato, coppie senza
# coordinate comuni non disponibili. La matrice finale resta completa
# soltanto se ogni coppia ha almeno un contributo.
csv_pair = (
    "a,b,c\n"
    "0,,\n"
    ",2,3\n"
    "4,5,\n"
    "1,,3\n"
)
dati_pair = p.prepara_tabella(p.leggi_csv(csv_pair))
risposte_pair = {
    "riga": "oggetto",
    "gestioneDipendenzaLineare": "mantieni",
    "confrontoQuantitativo": "assoluto",
    "misuraNumericaManuale": "weighted_minkowski",
    "ordineMisuraManuale": "2",
    "pesiMisuraManuale": "1; 2; 3",
    "colonne": {nome: {"ruolo": "quantita", "usa": True} for nome in ("a", "b", "c")},
    "mancantiNumericiPerColonna": {nome: "pairwise" for nome in ("a", "b", "c")},
    "significatoMancanti": "sconosciuto",
}
piano_pair = p.crea_piano_confronto(dati_pair, risposte_pair)
assert piano_pair["completo"], piano_pair
percorso_pair = piano_pair["percorsi"][0]
vettori_pair, indici_pair = p._righe_numeriche_per_percorso(dati_pair, percorso_pair)
assert len(vettori_pair) == 4 and indici_pair == [0, 1, 2, 3]
assert vettori_pair[0][1] is None and vettori_pair[0][2] is None
locale_pair = p.calcola_matrice_numerica(dati_pair, risposte_pair)
assert locale_pair["matrice"][0][1] is None
assert locale_pair["matrice"][0][2] is not None
assert locale_pair["matrice"][1][2] is not None
try:
    p.calcola_matrice(dati_pair, risposte_pair)
    assert False, "La matrice finale incompleta deve essere bloccata."
except ValueError as errore:
    assert "coppie non hanno alcun contributo valido" in str(errore)
assert not p.crea_piano_confronto(
    dati_pair, {**risposte_pair, "misuraNumericaManuale": "mahalanobis"}
)["completo"]
assert not p.crea_piano_confronto(
    dati_pair, {**risposte_pair, "misuraNumericaManuale": "canberra"}
)["completo"]

# Blocchi disgiunti: il confronto pairwise di un gruppo di coordinate
# può non avere contributo, mentre un secondo gruppo copre la coppia.
csv_blocchi_pair = (
    "a,b,c,p1,p2,p3\n"
    "0,,0,1,3,2\n"
    "3,4,,2,1,4\n"
    "6,4,3,3,4,1\n"
    ",8,9,4,2,1\n"
    ",,,2,3,4\n"
)
dati_blocchi_pair = p.prepara_tabella(p.leggi_csv(csv_blocchi_pair))
risposte_blocchi_pair = {
    "riga": "oggetto",
    "significatoMancanti": "sconosciuto",
    "significatoEstremi": "reali",
    "colonne": {nome: {"ruolo": "quantita", "usa": True}
                for nome in ("a", "b", "c", "p1", "p2", "p3")},
    "gruppi": [
        {"id": "coord", "nome": "Coordinate", "tipo": "coordinate"},
        {"id": "profilo", "nome": "Profilo", "tipo": "ripetute"},
    ],
    "assegnazioni": {
        **{nome: "coord" for nome in ("a", "b", "c")},
        **{nome: "profilo" for nome in ("p1", "p2", "p3")},
    },
    "misureGruppi": {"coord": "weighted_minkowski"},
    "ordiniGruppi": {"coord": "2"},
    "pesiGruppi": {"coord": "1; 2; 3"},
    "mancanti-gruppo-coord": "pairwise",
    "somiglianza-profilo": "andamento",
}
piano_blocchi_pair = p.crea_piano_confronto(dati_blocchi_pair, risposte_blocchi_pair)
assert piano_blocchi_pair["completo"], piano_blocchi_pair
assert piano_blocchi_pair["conteggioPercorsi"] == 2
percorso_coord = next(percorso for percorso in piano_blocchi_pair["percorsi"]
                     if percorso.get("idGruppo") == "coord")
matrice_coord = p._calcola_matrice_specializzata(
    dati_blocchi_pair, risposte_blocchi_pair, percorso_coord
)["matrice"]
assert matrice_coord[0][4] is None
assert matrice_coord[0][1] is not None
matrice_blocchi_pair = p.calcola_matrice(dati_blocchi_pair, risposte_blocchi_pair)
verifica_matrice_finale(matrice_blocchi_pair, 5)
assert all(x is not None and 0 <= x <= 1 for row in matrice_blocchi_pair["matrice"] for x in row)
assert not p.crea_piano_confronto(
    dati_blocchi_pair,
    {**risposte_blocchi_pair, "misureGruppi": {"coord": "euclidean"},
     "mancanti-gruppo-coord": "interpola_lineare"},
)["completo"]


# Coerenza tra riscalamenti confermati e misura scelta.
# Originali per Pearson e DTW richiedono una conferma distinta da quella
# generale: non possono ignorare il preprocessing in silenzio.
risposte_senza_conferma_originali = {
    **risposte_blocchi_eterogenei, "confermeValoriOriginaliGruppi": {},
}
piano_senza_conferma_originali = p.crea_piano_confronto(
    dati_blocchi_eterogenei, risposte_senza_conferma_originali
)
assert not piano_senza_conferma_originali["completo"]
gruppi_senza_conferma = {
    percorso["idGruppo"]: percorso
    for percorso in piano_senza_conferma_originali["percorsi"]
    if percorso["tipo"] == "gruppo"
}
for id_gruppo in ("tempo", "profilo"):
    assert gruppi_senza_conferma[id_gruppo]["compatibilitaPreelaborazione"]["richiesta"] == "originali_gruppo"
    assert not gruppi_senza_conferma[id_gruppo]["compatibilitaPreelaborazione"]["confermata"]
    assert gruppi_senza_conferma[id_gruppo]["stato"] == "da_completare"
assert gruppi_senza_conferma["coordinate"]["compatibilitaPreelaborazione"]["richiesta"] is None

# Piu' trasformazioni all'interno dello stesso gruppo di coordinate:
# consentite, ma solo dopo una conferma aggiuntiva.
scelte_scalatura_diversa = [
    {"tipo": "auto", "metodo": "auto"} for _ in range(6)
] + [
    {"tipo": "auto", "metodo": "nessuno"},
    {"tipo": "auto", "metodo": "zscore"},
]
dati_scalatura_diversa = p.prepara_tabella(
    p.leggi_csv(csv_blocchi_eterogenei), scelte_scalatura_diversa
)
piano_scalatura_diversa = p.crea_piano_confronto(
    dati_scalatura_diversa, risposte_blocchi_eterogenei
)
assert not piano_scalatura_diversa["completo"]
coord_non_confermato = next(
    percorso for percorso in piano_scalatura_diversa["percorsi"]
    if percorso.get("idGruppo") == "coordinate"
)
assert coord_non_confermato["compatibilitaPreelaborazione"]["richiesta"] == "misti_gruppo"
assert not coord_non_confermato["compatibilitaPreelaborazione"]["confermata"]
risposte_scalatura_confermata = {
    **risposte_blocchi_eterogenei,
    "confermeRiscalamentiMistiGruppi": {"coordinate": "si"},
}
piano_scalatura_confermata = p.crea_piano_confronto(
    dati_scalatura_diversa, risposte_scalatura_confermata
)
assert piano_scalatura_confermata["completo"], piano_scalatura_confermata
matrice_scalatura_confermata = p.calcola_matrice(
    dati_scalatura_diversa, risposte_scalatura_confermata
)
verifica_matrice_finale(matrice_scalatura_confermata, 5)

# Una misura relativa sulle coordinate INDIPENDENTI non deve ignorare
# riscalamenti già confermati senza ulteriore approvazione.
dati_misura_relativa = p.prepara_tabella(p.leggi_csv(
    "a,b\n1,8\n2,4\n3,9\n4,2\n5,7\n6,3\n7,10\n8,5\n9,6\n10,1"
))
risposte_relativa = {
    "riga": "oggetto",
    "confrontoQuantitativo": "relativo",
    "valoriVicinoZero": "no",
    "misuraNumericaManuale": "canberra",
    "riscalamentoConfermato": True,
    "colonne": {nome: {"ruolo": "quantita", "usa": True} for nome in ("a", "b")},
}
piano_relativa = p.crea_piano_confronto(dati_misura_relativa, risposte_relativa)
assert not piano_relativa["completo"]
assert piano_relativa["percorsi"][0]["compatibilitaPreelaborazione"]["richiesta"] == "originali_numerico"
piano_relativa_confermata = p.crea_piano_confronto(
    dati_misura_relativa,
    {**risposte_relativa, "confermaValoriOriginaliNumerici": "si"},
)
assert piano_relativa_confermata["completo"], piano_relativa_confermata
assert not piano_relativa_confermata["percorsi"][0]["preelaborazione"]["usaTabellaTrasformata"]
assert piano_relativa_confermata["percorsi"][0]["compatibilitaPreelaborazione"]["confermata"]


# La diagnostica non deve modificare riscalamenti o selezionare
# automaticamente una misura diversa.
stats_asimmetriche = p.statistiche([float(i**3) for i in range(1, 41)])
assert stats_asimmetriche["numeroOsservati"] == 40
assert stats_asimmetriche["asimmetriaBowley"] > .3
stats_simmetriche = p.statistiche([float(i) for i in range(-20, 21)])
quasi_uguali(stats_simmetriche["asimmetriaBowley"], 0)
assert p.statistiche([4, 4, 4, 4])["asimmetriaBowley"] is None

# Outlier soltanto multivariato: la singola coordinata non e' estrema,
# ma (9,1) si discosta nettamente dalla relazione fra le due colonne.
csv_joint = (
    "x,y\n"
    + "".join(
        f"{i / 3},{i / 3 + ((i % 3) - 1) * .15}\n" for i in range(1, 31)
    )
    + "9,1\n"
)
tabella_joint = p.prepara_tabella(p.leggi_csv(csv_joint))
diagnosi_joint = p._diagnosi_numerica(
    ["x", "y"], {c["nome"]: c for c in tabella_joint["colonne"]}
)
assert diagnosi_joint["diagnosiMultivariata"]["stato"] == "valutata", diagnosi_joint
assert diagnosi_joint["diagnosiMultivariata"]["numeroCandidati"] >= 1
assert any(c["riga"] == 31 for c in diagnosi_joint["diagnosiMultivariata"]["candidati"])
assert diagnosi_joint["diagnosiMultivariata"]["soglia"] > 0
assert not any(c["statistiche"]["estremi"] for c in tabella_joint["colonne"])
risposte_joint = risposte_quantitative(
    significatoEstremi="reali",
    gestioneDipendenzaLineare="mantieni",
)
piano_joint = p.crea_piano_confronto(tabella_joint, risposte_joint)
assert piano_joint["completo"], piano_joint
assert p.crea_piano_confronto(
    tabella_joint, {**risposte_joint, "significatoEstremi": ""}
)["completo"] is False
assert p.crea_piano_confronto(
    tabella_joint, {**risposte_joint, "significatoEstremi": "controllare"}
)["completo"] is False

# La mancata applicabilita' dell'analisi congiunta non viene spacciata
# per assenza di anomalie (campione piccolo o covarianza singolare).
diagnosi_poche = p._diagnosi_numerica(
    ["a", "b"], {c["nome"]: c for c in scale_simili["colonne"]}
)
assert diagnosi_poche["diagnosiMultivariata"]["stato"] == "non_valutabile"
diagnosi_singolare = p._diagnosi_numerica(
    ["a", "b"], {c["nome"]: c for c in scale_diverse["colonne"]}
)
assert diagnosi_singolare["diagnosiMultivariata"]["stato"] == "non_valutabile"


# Le scelte manuali sul preprocessing precedono ogni politica automatica.
# log(1+x) e' una trasformazione, non una standardizzazione.
csv_log = (
    "a,b\n"
    "0,3\n1,8\n2,6\n3,4\n4,7\n5,9\n"
    "6,1\n7,10\n8,2\n20,5\n"
)
orig_log = p.prepara_tabella(p.leggi_csv(csv_log))
scelte_log = [
    {"tipo": "auto", "metodo": "log1p"},
    {"tipo": "auto", "metodo": "nessuno"},
]
scelte_robuste_manuali = [
    {"tipo": "auto", "metodo": "robusto"},
    {"tipo": "auto", "metodo": "nessuno"},
]
preparata_log = p.prepara_tabella(p.leggi_csv(csv_log), scelte_log)
assert preparata_log["colonne"][0]["sceltaMetodo"] == "log1p"
assert preparata_log["colonne"][1]["sceltaMetodo"] == "nessuno"
quasi_uguali(preparata_log["trasformate"][0][0], 0)
quasi_uguali(preparata_log["trasformate"][1][0], math.log(2))
quasi_uguali(preparata_log["trasformate"][9][0], math.log(21))
assert [riga[1] for riga in preparata_log["trasformate"]] == [
    3, 8, 6, 4, 7, 9, 1, 10, 2, 5,
]
analisi_log = {c["nome"]: c for c in preparata_log["colonne"]}
for forzato in ("zscore", "robusto", "minmax", "maxabs"):
    preprocessamento = p._preelaborazione_numerica(
        ["a", "b"], analisi_log, forzato
    )
    assert [t["metodo"] for t in preprocessamento["passi"]] == [
        "log1p", "nessuno"
    ], (forzato, preprocessamento)
risposte_log = {
    **risposte_automatiche(["a", "b"]),
    "riscalamentoConfermato": True,
    "gestioneDipendenzaLineare": "mantieni",
    "misuraNumericaManuale": "euclidean",
}
piano_log = p.crea_piano_confronto(preparata_log, risposte_log)
assert piano_log["completo"], piano_log
assert [v["metodo"] for v in piano_log["percorsi"][0]["preelaborazione"]["passi"]] == [
    "log1p", "nessuno"
]
matrice_log = p.calcola_matrice_numerica(preparata_log, risposte_log)
# Prima coordinata logaritmica, seconda originale: Euclidea senza pesi.
quasi_uguali(
    matrice_log["matrice"][0][1],
    math.hypot(math.log1p(1)-math.log1p(0), 8-3),
)
piano_orig = p.crea_piano_confronto(orig_log, risposte_log)
assert piano_orig["completo"], piano_orig
assert p.calcola_matrice_numerica(orig_log, risposte_log)["matrice"] != matrice_log["matrice"]

# La trasformazione log(1+x) non puo' essere applicata a valori negativi,
# nemmeno se la misura di distanza successiva sarebbe ben definita.
try:
    p.prepara_tabella(
        p.leggi_csv("a,b\n-1,2\n0,3\n1,4"),
        [{"tipo": "auto", "metodo": "log1p"}, {}],
    )
    assert False, "log(1+x) deve essere rifiutato sui dati negativi"
except ValueError as errore:
    assert "non negativi" in str(errore) or "maggior" in str(errore)

# Conferma che il metodo robusto esplicito non diventi z-score.
preparata_robusta = p.prepara_tabella(
    p.leggi_csv(csv_log), scelte_robuste_manuali
)
piano_robusta = p.crea_piano_confronto(preparata_robusta, risposte_log)
assert piano_robusta["completo"], piano_robusta
assert [v["metodo"] for v in piano_robusta["percorsi"][0]["preelaborazione"]["passi"]] == [
    "robusto", "nessuno"
]

# Normalizzazione robusta per blocco: max su righe non anomale confermate,
# saturazione dei soli confronti oltre tale max, nessuna riga eliminata.
locale_norma = {
    "matrice": [
        [0.0, 1.0, 2.0, 30.0],
        [1.0, 0.0, 1.0, 29.0],
        [2.0, 1.0, 0.0, 28.0],
        [30.0, 29.0, 28.0, 0.0],
    ],
    "indiciRighe": [0, 1, 2, 3],
    "limiteAggregazione": None,
}
conf_robusta = {"metodo": "robusta", "righeAnomale": [4]}
matrice_robusta, criterio_robusto, info_robusto = (
    p._normalizza_per_aggregazione_con_diagnostica(locale_norma, conf_robusta)
)
quasi_uguali(info_robusto["scala"], 2)
quasi_uguali(matrice_robusta[0][1], .5)
quasi_uguali(matrice_robusta[0][2], 1)
quasi_uguali(matrice_robusta[1][3], 1)
assert info_robusto["coppieSaturate"] == 3
assert "massimo robusto" in criterio_robusto
norma_campionaria, _, _ = p._normalizza_per_aggregazione_con_diagnostica(
    locale_norma, {"metodo": "campionaria"}
)
quasi_uguali(norma_campionaria[0][1], 1 / 30)
assert norma_campionaria != matrice_robusta

# Conserva gli indici ORIGINALI, anche se il percorso ha escluso righe
# per altri motivi e le posizioni nella matrice sono diverse.
locale_indici = {
    "matrice": [
        [0.0, 2.0, 40.0],
        [2.0, 0.0, 35.0],
        [40.0, 35.0, 0.0],
    ],
    "indiciRighe": [0, 2, 4],
    "limiteAggregazione": None,
}
vettore_norm, _, info_indici = p._normalizza_per_aggregazione_con_diagnostica(
    locale_indici, {"metodo": "robusta", "righeAnomale": [5]}
)
quasi_uguali(vettore_norm[0][1], 1)
assert info_indici["coppieSaturate"] == 2

for errata in (
    {"metodo": "robusta", "righeAnomale": []},
    {"metodo": "robusta", "righeAnomale": [1, 2, 3]},
    {"metodo": "sconosciuta"},
):
    try:
        p._normalizza_per_aggregazione_con_diagnostica(locale_norma, errata)
        assert False, "La normalizzazione errata deve fallire."
    except ValueError:
        pass
try:
    p._normalizza_per_aggregazione_con_diagnostica(
        {"matrice": [[0, 0], [0, 0]], "limiteAggregazione": None},
        {"metodo": "robusta", "righeAnomale": [2]},
    )
    assert False, "Servono almeno due osservazioni non anomale."
except ValueError:
    pass

# Non ripiega dal massimo robusto zero al massimo campionario.
try:
    p._normalizza_per_aggregazione_con_diagnostica(
        {
            "matrice": [[0, 0, 7], [0, 0, 8], [7, 8, 0]],
            "indiciRighe": [0, 1, 2], "limiteAggregazione": None,
        }, {"metodo": "robusta", "righeAnomale": [3]}
    )
    assert False, "Un massimo robusto nullo con distanze positive deve bloccare."
except ValueError as errore:
    assert "scala robusta" in str(errore)
# Blocco interamente costante: conserva i contributi a zero.
nulla_robusta, _, info_nulla = p._normalizza_per_aggregazione_con_diagnostica(
    {"matrice": [[0, 0, 0], [0, 0, 0], [0, 0, 0]],
     "indiciRighe": [0, 1, 2], "limiteAggregazione": None},
    {"metodo": "robusta", "righeAnomale": [3]},
)
assert all(valore == 0 for riga in nulla_robusta for valore in riga)
assert info_nulla["coppieSaturate"] == 0

# Scala naturale preesistente: nessuna amplificazione campionaria.
bray_con_limite = p.crea_piano_confronto(
    scale_simili,
    {**risposte_accessibili, "confrontoQuantitativo": "abbondanza"},
)
assert bray_con_limite["percorsi"][0]["normalizzazione"]["metodo"] == "teorica"
assert bray_con_limite["percorsi"][0]["normalizzazione"]["limiteTeorico"] == 1
piano_br_illecito = p.crea_piano_confronto(
    scale_simili,
    {**risposte_accessibili, "confrontoQuantitativo": "abbondanza",
     "normalizzazioniPercorsi": {"percorso-1": "robusta"},
     "righeAnomaleNormalizzazione": {"percorso-1": "3"}},
)
assert not piano_br_illecito["completo"]
assert not piano_br_illecito["percorsi"][0]["normalizzazione"]["valida"]

# Percorso singolo: modifica realmente l'output mantenendo tutte le righe.
dati_con_estremo_norm = p.prepara_tabella(p.leggi_csv(
    "x,id\n0,a\n1,b\n2,c\n3,d\n40,e"
))
base_estremo_norm = {
    "riga": "oggetto",
    "significatoEstremi": "reali",
    "confrontoQuantitativo": "assoluto",
    "misuraNumericaManuale": "euclidean",
    "colonne": {"x": {"ruolo": "quantita", "usa": True}},
}
piano_robusto_incompleto = p.crea_piano_confronto(
    dati_con_estremo_norm,
    {**base_estremo_norm, "normalizzazioniPercorsi": {"percorso-1": "robusta"}},
)
assert not piano_robusto_incompleto["completo"]
for stringa_errata in ("0", "6", "5;5", "1;2;3;4"):
    assert not p.crea_piano_confronto(
        dati_con_estremo_norm,
        {**base_estremo_norm,
         "normalizzazioniPercorsi": {"percorso-1": "robusta"},
         "righeAnomaleNormalizzazione": {"percorso-1": stringa_errata}},
    )["completo"]
confermate_estremo = {
    **base_estremo_norm,
    "normalizzazioniPercorsi": {"percorso-1": "robusta"},
    "righeAnomaleNormalizzazione": {"percorso-1": "5"},
}
piano_robusto_ok = p.crea_piano_confronto(
    dati_con_estremo_norm, confermate_estremo
)
assert piano_robusto_ok["completo"], piano_robusto_ok
matrice_con_robusto = p.calcola_matrice(dati_con_estremo_norm, confermate_estremo)
matrice_con_max = p.calcola_matrice(dati_con_estremo_norm, base_estremo_norm)
quasi_uguali(matrice_con_robusto["matrice"][0][1], 1 / 3)
quasi_uguali(matrice_con_max["matrice"][0][1], 1 / 40)
quasi_uguali(matrice_con_robusto["matrice"][0][4], 1)
assert len(matrice_con_robusto["etichette"]) == 5
assert matrice_con_robusto["normalizzazioneFinale"]["coppieSaturate"] > 0
assert matrice_con_robusto["diagnosticaFinale"]["avvisi"]

# Vari percorsi: solo il blocco indicato dall'utente riceve scala robusta.
risposte_blocchi_norm = {
    **risposte_blocchi_eterogenei,
    "normalizzazioniPercorsi": {"percorso-3": "robusta"},
    "righeAnomaleNormalizzazione": {"percorso-3": "4"},
}
piano_blocchi_norm = p.crea_piano_confronto(
    dati_blocchi_eterogenei, risposte_blocchi_norm
)
assert piano_blocchi_norm["completo"], piano_blocchi_norm
assert [
    v["normalizzazione"]["metodo"] for v in piano_blocchi_norm["percorsi"]
] == ["campionaria", "teorica", "robusta"]
composita_norm = p.calcola_matrice(dati_blocchi_eterogenei, risposte_blocchi_norm)
verifica_matrice_finale(composita_norm, 5)
assert [c["diagnosticaNormalizzazione"]["metodo"] for c in composita_norm["contributi"]] == [
    "campionaria", "teorica", "robusta"
]

print("Tutti i test Python di preprocessing sono stati superati.")
