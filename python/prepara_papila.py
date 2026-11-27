"""Unisce i due fogli clinici PAPILA in un CSV con una riga per paziente.

Uso: python python/prepara_papila.py patient_data_od.xlsx patient_data_os.xlsx FundusImages papila.csv
Richiede openpyxl. Le immagini restano nella cartella originale e si caricano
separatamente nel sito; il CSV contiene soltanto i loro nomi.
"""

import argparse
import csv
import re
from pathlib import Path

from openpyxl import load_workbook


def leggi_foglio(percorso):
    foglio = load_workbook(percorso, read_only=True, data_only=True).active
    righe = foglio.values
    intestazioni = next(righe)
    if not intestazioni or intestazioni[0] != "ID" or "Diagnosis" not in intestazioni:
        raise ValueError(f"Intestazioni PAPILA inattese in {percorso}")
    dati = {}
    for valori in righe:
        identita = str(valori[0] or "").strip()
        if not identita:
            continue
        if not re.fullmatch(r"#\d{3}", identita) or identita in dati:
            raise ValueError(f"ID non valido o ripetuto in {percorso}: {identita}")
        dati[identita] = dict(zip(intestazioni, valori))
    return tuple(intestazioni), dati


def prepara(od, os, cartella_immagini, destinazione):
    nomi_od, dati_od = leggi_foglio(od)
    nomi_os, dati_os = leggi_foglio(os)
    if nomi_od != nomi_os or set(dati_od) != set(dati_os):
        raise ValueError("I fogli OD e OS hanno colonne o pazienti differenti")
    cartella = Path(cartella_immagini)
    immagini = {p.name.lower(): p.name for p in cartella.rglob("*") if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}}
    colonne = ["patient_id"] + [f"{nome}_{occhio}" for occhio in ("OD", "OS") for nome in nomi_od if nome != "ID"] + ["image_OD", "image_OS"]
    righe = []
    for identita in sorted(dati_od):
        destro, sinistro = dati_od[identita], dati_os[identita]
        # La raccolta contiene anche un record privo di diagnosi per entrambi gli occhi.
        if destro["Diagnosis"] is None or sinistro["Diagnosis"] is None:
            continue
        numero = identita[1:]
        foto = []
        for occhio in ("OD", "OS"):
            candidati = [immagini.get(f"ret{numero}{occhio.lower()}{estensione}") for estensione in (".jpg", ".jpeg", ".png", ".webp")]
            trovate = [nome for nome in candidati if nome]
            if len(trovate) != 1:
                raise ValueError(f"Attesa una fotografia per {identita} {occhio}; trovate {len(trovate)}")
            foto.append(trovate[0])
        righe.append([f"RET{numero}"] + [dati[nome] if dati[nome] is not None else "" for dati in (destro, sinistro) for nome in nomi_od if nome != "ID"] + foto)
    with open(destinazione, "w", encoding="utf-8", newline="") as uscita:
        scrittore = csv.writer(uscita)
        scrittore.writerow(colonne)
        scrittore.writerows(righe)
    return len(righe)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for argomento in ("od", "os", "cartella_immagini", "destinazione"):
        parser.add_argument(argomento, type=Path)
    parametri = parser.parse_args()
    print(f"Creato CSV con {prepara(parametri.od, parametri.os, parametri.cartella_immagini, parametri.destinazione)} pazienti")
