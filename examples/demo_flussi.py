"""Dimostrazione sintetica dei principali percorsi decisionali.

Esecuzione dalla radice del progetto:
    python3 examples/demo_flussi.py

Non sostituisce la suite di test: stampa in forma leggibile i segnali
diagnostici, la decisione locale, la normalizzazione e l'esito finale.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
import preprocessing as p  # noqa: E402

FIXTURE = ROOT / "examples" / "collaudo"


def carica(nome: str):
    testo = (FIXTURE / nome).read_text(encoding="utf-8")
    return p.prepara_tabella(p.leggi_csv(testo))


def numeriche(nomi: tuple[str, ...]) -> dict:
    return {
        "riga": "oggetto",
        "significatoEstremi": "reali",
        "confrontoQuantitativo": "assoluto",
        "colonne": {
            nome: {"ruolo": "quantita", "usa": True} for nome in nomi
        },
    }


def stampa_piano(titolo: str, dati, risposte: dict, *, calcola: bool = True) -> None:
    piano = p.crea_piano_confronto(dati, risposte)
    print(f"\n{'=' * 72}\n{titolo}\n{'=' * 72}")
    print("Famiglia:", piano["diagnosi"]["famiglia"])
    proposta = piano["diagnosi"]["proposta"]
    print("Proposta:", proposta["misura"])
    print("Motivo:", proposta["motivo"])
    print("Piano completo:", "sì" if piano["completo"] else "no")
    for percorso in piano["percorsi"]:
        print(
            f"- {percorso['titolo']}: {percorso['metodo']} | "
            f"colonne={', '.join(percorso['colonne'])} | "
            f"normalizzazione={percorso['normalizzazione']['metodo']} | "
            f"peso={percorso['pesoAggregazione']}"
        )
        for avviso in percorso.get("avvisi", []):
            print("  avviso:", avviso)
    for avviso in piano["avvisi"]:
        print("Decisione richiesta:", avviso)
    if calcola and piano["completo"]:
        risultato = p.calcola_matrice(dati, risposte)
        diagnostica = risultato["diagnosticaFinale"]
        print("Esito:", risultato["metodo"])
        print(
            "Matrice:", f"{len(risultato['matrice'])}×{len(risultato['matrice'])}",
            "| coppie confrontabili:", diagnostica["coppieTotali"],
            "| coppie non disponibili:", diagnostica["coppieNonDisponibili"],
        )
        print("Prima riga:", risultato["matrice"][0])


stampa_piano(
    "1. Quantità ordinarie: proposta euclidea",
    carica("01_numerici_ordinari.csv"),
    numeriche(("a", "b")),
)

dati_singolari = carica("04_numerici_covarianza_singolare.csv")
risposte_singolari = numeriche(("a", "b"))
stampa_piano(
    "2A. Colonne proporzionali: decisione ancora necessaria",
    dati_singolari,
    risposte_singolari,
    calcola=False,
)
stampa_piano(
    "2B. Colonne proporzionali: mantenute consapevolmente",
    dati_singolari,
    {**risposte_singolari, "gestioneDipendenzaLineare": "mantieni"},
)

stampa_piano(
    "3. Dati misti: Gower classica",
    carica("06_dati_misti.csv"),
    {
        "riga": "persona",
        "zeriCondivisi": "si",
        "gestioneQuantitativeMiste": "gower",
        "colonne": {},
    },
)

print(
    "\nScenario avanzato: esegui `python3 test/test_integrazione.py` per "
    "quattro percorsi simultanei, mancanti pairwise, pesi e scala robusta."
)
