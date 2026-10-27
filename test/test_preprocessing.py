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

assert p.crea_csv(["a", "b"], [[1.25, "x,y"]]) == 'a,b\n1.25,"x,y"'

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

print("Tutti i test Python di preprocessing sono stati superati.")
