"""Analisi e riscalamento di tabelle CSV eseguiti interamente in Python."""

from __future__ import annotations

import csv
import io
import json
import math
import re
from typing import Any


MANCANTI = {"", "na", "n/a", "null", "?"}
INVALIDO = object()
NUMERO_PUNTO = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")
NUMERO_VIRGOLA = re.compile(r"^[+-]?(?:\d+(?:,\d*)?|,\d+)(?:[eE][+-]?\d+)?$")


def _prima_riga(testo: str) -> str:
    dentro_virgolette = False
    risultato: list[str] = []
    i = 0
    while i < len(testo):
        carattere = testo[i]
        if carattere == '"':
            if dentro_virgolette and i + 1 < len(testo) and testo[i + 1] == '"':
                risultato.extend(['"', '"'])
                i += 2
                continue
            dentro_virgolette = not dentro_virgolette
        if not dentro_virgolette and carattere in "\r\n":
            break
        risultato.append(carattere)
        i += 1
    return "".join(risultato)


def _conta_separatore(riga: str, separatore: str) -> int:
    dentro_virgolette = False
    conteggio = 0
    i = 0
    while i < len(riga):
        if riga[i] == '"':
            if dentro_virgolette and i + 1 < len(riga) and riga[i + 1] == '"':
                i += 2
                continue
            dentro_virgolette = not dentro_virgolette
        elif not dentro_virgolette and riga[i] == separatore:
            conteggio += 1
        i += 1
    return conteggio


def rileva_separatore(testo: str) -> str:
    prima = _prima_riga(testo.lstrip("\ufeff"))
    candidati = [(separatore, _conta_separatore(prima, separatore)) for separatore in (",", ";", "\t")]
    separatore, conteggio = max(candidati, key=lambda elemento: elemento[1])
    if conteggio == 0:
        raise ValueError(
            "Non riesco a individuare il separatore del CSV. "
            "Usa virgola, punto e virgola oppure tabulazione."
        )
    return separatore


def leggi_csv(testo: str) -> dict[str, Any]:
    if not isinstance(testo, str) or not testo.strip():
        raise ValueError("Il file CSV è vuoto.")

    pulito = testo.lstrip("\ufeff")
    separatore = rileva_separatore(pulito)
    try:
        lettore = csv.reader(io.StringIO(pulito, newline=""), delimiter=separatore, strict=True)
        righe = [[campo.strip() for campo in riga] for riga in lettore]
    except csv.Error as errore:
        raise ValueError(f"Il CSV non è valido: {errore}.") from errore

    righe = [riga for riga in righe if any(campo != "" for campo in riga)]
    if len(righe) < 2:
        raise ValueError("Il CSV deve contenere un'intestazione e almeno una riga di dati.")

    intestazioni = righe[0]
    if any(not nome for nome in intestazioni):
        raise ValueError("Tutte le colonne devono avere un titolo.")
    normalizzate = [nome.casefold() for nome in intestazioni]
    if len(set(normalizzate)) != len(normalizzate):
        raise ValueError("I titoli delle colonne devono essere univoci.")

    dati = righe[1:]
    for indice, riga in enumerate(dati, start=2):
        if len(riga) != len(intestazioni):
            raise ValueError(
                f"La riga {indice} contiene {len(riga)} campi anziché {len(intestazioni)}."
            )
    if len(dati) * len(intestazioni) > 2_000_000:
        raise ValueError("La tabella supera il limite iniziale di 2.000.000 di celle.")

    return {"intestazioni": intestazioni, "righe": dati, "separatore": separatore}


def mancante(valore: Any) -> bool:
    return valore is None or str(valore).strip().casefold() in MANCANTI


def leggi_numero(valore: Any, separatore: str = ",") -> float | None | object:
    if mancante(valore):
        return None
    testo = str(valore).strip()
    if NUMERO_PUNTO.fullmatch(testo):
        numero = float(testo)
        return numero if math.isfinite(numero) else INVALIDO
    if separatore != "," and NUMERO_VIRGOLA.fullmatch(testo):
        numero = float(testo.replace(",", "."))
        return numero if math.isfinite(numero) else INVALIDO
    return INVALIDO


def quantile(ordinati: list[float], probabilita: float) -> float | None:
    if not ordinati:
        return None
    posizione = (len(ordinati) - 1) * probabilita
    sotto = math.floor(posizione)
    sopra = math.ceil(posizione)
    if sotto == sopra:
        return ordinati[sotto]
    return ordinati[sotto] + (ordinati[sopra] - ordinati[sotto]) * (posizione - sotto)


def statistiche(valori: list[float]) -> dict[str, float | int]:
    ordinati = sorted(valori)
    media = sum(valori) / len(valori)
    varianza = sum((valore - media) ** 2 for valore in valori) / len(valori)
    deviazione = math.sqrt(varianza)
    mediana = quantile(ordinati, 0.5)
    q1 = quantile(ordinati, 0.25)
    q3 = quantile(ordinati, 0.75)
    assert mediana is not None and q1 is not None and q3 is not None
    iqr = q3 - q1
    minimo_tukey = q1 - 1.5 * iqr
    massimo_tukey = q3 + 1.5 * iqr
    estremi = sum(valore < minimo_tukey or valore > massimo_tukey for valore in valori)
    zeri = sum(valore == 0 for valore in valori)
    massimo_assoluto = max(abs(valore) for valore in valori)
    return {
        "media": media,
        "deviazione": deviazione,
        "mediana": mediana,
        "q1": q1,
        "q3": q3,
        "iqr": iqr,
        "minimo": ordinati[0],
        "massimo": ordinati[-1],
        "massimoAssoluto": massimo_assoluto,
        "estremi": estremi,
        "quotaEstremi": estremi / len(valori),
        "zeri": zeri,
        "quotaZeri": zeri / len(valori),
    }


def descrivi_outlier(stats: dict[str, Any]) -> str:
    if stats["estremi"] == 1:
        return "È presente un solo outlier."
    if stats["quotaEstremi"] <= 0.1:
        return "Sono presenti pochi outlier."
    return "Sono presenti molti outlier."


def analizza_colonna(nome: str, valori: list[str], separatore: str) -> dict[str, Any]:
    convertiti = [leggi_numero(valore, separatore) for valore in valori]
    osservati = [valore for valore in convertiti if valore is not None]
    tutti_numerici = bool(osservati) and all(valore is not INVALIDO for valore in osservati)
    mancanti = sum(valore is None for valore in convertiti)

    if not tutti_numerici:
        return {
            "nome": nome,
            "tipo": "non_numerica",
            "metodo": "nessuno",
            "mancanti": mancanti,
            "motivo": "Sono presenti valori non numerici.",
        }

    numeri = [float(valore) for valore in osservati]
    if all(valore in (0, 1) for valore in set(numeri)):
        return {
            "nome": nome,
            "tipo": "binaria",
            "metodo": "nessuno",
            "mancanti": mancanti,
            "motivo": "Sono presenti soltanto 0 e 1.",
            "valoriNumerici": convertiti,
        }

    stats = statistiche(numeri)
    if stats["deviazione"] == 0:
        return {
            "nome": nome,
            "tipo": "numerica_costante",
            "metodo": "costante",
            "mancanti": mancanti,
            "motivo": "Tutti i valori sono uguali.",
            "statistiche": stats,
            "valoriNumerici": convertiti,
        }

    robusto = stats["quotaEstremi"] > 0.01 and stats["iqr"] > 0
    maxabs = not robusto and stats["quotaZeri"] >= 0.8 and stats["massimoAssoluto"] > 0
    metodo = "robusto" if robusto else "maxabs" if maxabs else "zscore"
    motivo = (
        descrivi_outlier(stats)
        if robusto
        else "Molti valori sono uguali a zero."
        if maxabs
        else "I valori sono concentrati su pochi livelli."
        if stats["iqr"] == 0
        else "Non emergono outlier rilevanti."
    )
    return {
        "nome": nome,
        "tipo": "numerica",
        "metodo": metodo,
        "mancanti": mancanti,
        "motivo": motivo,
        "statistiche": stats,
        "valoriNumerici": convertiti,
    }


def personalizza_colonna(
    nome: str,
    valori: list[str],
    separatore: str,
    scelta: dict[str, str] | None = None,
) -> dict[str, Any]:
    scelta = scelta or {}
    automatica = analizza_colonna(nome, valori, separatore)
    tipo_scelto = scelta.get("tipo") or "auto"
    metodo_scelto = scelta.get("metodo") or "auto"

    if tipo_scelto == "auto" and metodo_scelto == "auto":
        return {
            **automatica,
            "tipoRilevato": automatica["tipo"],
            "metodoAutomatico": automatica["metodo"],
            "sceltaTipo": "auto",
            "sceltaMetodo": "auto",
        }

    tipo = automatica["tipo"] if tipo_scelto == "auto" else tipo_scelto
    convertiti = [leggi_numero(valore, separatore) for valore in valori]
    osservati = [valore for valore in convertiti if valore is not None]
    mancanti = sum(valore is None for valore in convertiti)
    numerici_validi = bool(osservati) and all(valore is not INVALIDO for valore in osservati)
    metodo_automatico = automatica["metodo"]

    if tipo == "non_numerica":
        metodo_automatico = "nessuno"
        analisi = {
            "nome": nome,
            "tipo": tipo,
            "metodo": "nessuno",
            "mancanti": mancanti,
            "motivo": "I valori restano invariati.",
        }
    else:
        if not numerici_validi:
            descrizione = "binaria" if tipo == "binaria" else "numerica"
            raise ValueError(
                f"La feature “{nome}” contiene valori non numerici e non può essere trattata come {descrizione}."
            )
        numeri = [float(valore) for valore in osservati]
        if tipo == "binaria":
            if not all(valore in (0, 1) for valore in numeri):
                raise ValueError(
                    f"La feature “{nome}” non è binaria: sono ammessi soltanto 0, 1 e valori mancanti."
                )
            metodo_automatico = "nessuno"
            analisi = {
                "nome": nome,
                "tipo": tipo,
                "metodo": "nessuno",
                "mancanti": mancanti,
                "motivo": "Sono presenti soltanto 0 e 1.",
                "valoriNumerici": convertiti,
            }
        else:
            stats = statistiche(numeri)
            ha_estremi = stats["quotaEstremi"] > 0.01 and stats["iqr"] > 0
            sparsa = not ha_estremi and stats["quotaZeri"] >= 0.8 and stats["massimoAssoluto"] > 0
            automatico = (
                "costante"
                if stats["deviazione"] == 0
                else "robusto"
                if ha_estremi
                else "maxabs"
                if sparsa
                else "zscore"
            )
            metodo_automatico = automatico
            metodo = automatico if metodo_scelto == "auto" else metodo_scelto
            if metodo == "zscore" and stats["deviazione"] == 0:
                raise ValueError(
                    f"La feature “{nome}” è costante: lo z-score richiede una deviazione standard positiva."
                )
            if metodo == "robusto" and stats["iqr"] == 0:
                raise ValueError(f"La feature “{nome}” ha IQR nullo: la scala robusta non è definita.")
            if metodo == "minmax" and stats["massimo"] == stats["minimo"]:
                raise ValueError(
                    f"La feature “{nome}” è costante: min–max richiede massimo e minimo differenti."
                )
            if metodo == "maxabs" and stats["massimoAssoluto"] == 0:
                raise ValueError(
                    f"La feature “{nome}” contiene soltanto zeri: max-abs richiede un massimo assoluto positivo."
                )
            motivi = {
                "zscore": "Non emergono outlier rilevanti." if metodo_scelto == "auto" else "Le differenze vengono riportate su una scala comune.",
                "robusto": descrivi_outlier(stats) if metodo_scelto == "auto" else "Viene ridotto il peso degli outlier.",
                "maxabs": "Molti valori sono uguali a zero." if metodo_scelto == "auto" else "Gli zeri restano invariati.",
                "minmax": "I valori vengono riportati tra 0 e 1.",
                "costante": "Tutti i valori sono uguali.",
                "nessuno": "I valori restano invariati.",
            }
            analisi = {
                "nome": nome,
                "tipo": "numerica_costante" if stats["deviazione"] == 0 and metodo == "costante" else "numerica",
                "metodo": metodo,
                "mancanti": mancanti,
                "motivo": motivi[metodo],
                "statistiche": stats,
                "valoriNumerici": convertiti,
            }

    return {
        **analisi,
        "tipoRilevato": automatica["tipo"],
        "metodoAutomatico": metodo_automatico,
        "sceltaTipo": tipo_scelto,
        "sceltaMetodo": metodo_scelto,
    }


def applica_confronto_globale(colonne: list[dict[str, Any]]) -> None:
    numeriche = [
        colonna
        for colonna in colonne
        if colonna["tipo"] == "numerica"
        and colonna.get("statistiche")
        and colonna["statistiche"]["deviazione"] > 0
    ]
    if not numeriche:
        return

    scale = [
        colonna["statistiche"]["iqr"]
        if colonna["statistiche"]["iqr"] > 0
        else colonna["statistiche"]["deviazione"]
        for colonna in numeriche
    ]
    rapporto = 1 if len(numeriche) == 1 else max(scale) / min(scale)
    confrontabili = rapporto <= 2
    robusto_applicabile = all(colonna["statistiche"]["iqr"] > 0 for colonna in numeriche)
    presenti_outlier = robusto_applicabile and any(
        colonna["statistiche"]["quotaEstremi"] > 0.01 for colonna in numeriche
    )
    valori_osservati = sum(
        sum(valore is not None for valore in colonna["valoriNumerici"])
        for colonna in numeriche
    )
    zeri_osservati = sum(colonna["statistiche"]["zeri"] for colonna in numeriche)
    matrice_sparsa = (
        not presenti_outlier
        and valori_osservati > 0
        and zeri_osservati / valori_osservati >= 0.8
    )

    metodo_comune = (
        "robusto"
        if presenti_outlier
        else "maxabs"
        if matrice_sparsa
        else "nessuno"
        if confrontabili
        else "zscore"
    )

    for colonna in numeriche:
        colonna["metodoAutomatico"] = metodo_comune
        if colonna["sceltaMetodo"] != "auto":
            continue
        colonna["metodo"] = metodo_comune
        if metodo_comune == "robusto":
            colonna["motivo"] = (
                descrivi_outlier(colonna["statistiche"])
                if colonna["statistiche"]["quotaEstremi"] > 0.01
                else "È stata scelta una scala robusta comune per le feature numeriche."
            )
        elif metodo_comune == "maxabs":
            colonna["motivo"] = "La matrice numerica contiene molti valori uguali a zero."
        elif metodo_comune == "nessuno":
            colonna["motivo"] = (
                "Non ci sono altre feature numeriche con cui bilanciare la scala."
                if len(numeriche) == 1
                else "Le feature numeriche hanno dispersioni simili."
            )
        else:
            colonna["motivo"] = "Le feature numeriche hanno dispersioni molto diverse."


def trasforma_valore(valore: Any, analisi: dict[str, Any]) -> Any:
    if analisi["tipo"] == "non_numerica":
        return None if mancante(valore) else valore
    numero = leggi_numero(valore, analisi["separatore"])
    if numero is None:
        return None
    if numero is INVALIDO:
        raise ValueError(f"La feature “{analisi['nome']}” contiene un valore non numerico.")
    numero = float(numero)
    if analisi["tipo"] == "binaria" or analisi["metodo"] == "nessuno":
        return numero
    if analisi["metodo"] == "costante":
        return 0
    stats = analisi["statistiche"]
    if analisi["metodo"] == "robusto":
        return (numero - stats["mediana"]) / stats["iqr"]
    if analisi["metodo"] == "minmax":
        return (numero - stats["minimo"]) / (stats["massimo"] - stats["minimo"])
    if analisi["metodo"] == "maxabs":
        return numero / stats["massimoAssoluto"]
    return (numero - stats["media"]) / stats["deviazione"]


def prepara_tabella(tabella: dict[str, Any], scelte: list[dict[str, str]] | None = None) -> dict[str, Any]:
    scelte = scelte or []
    colonne: list[dict[str, Any]] = []
    for indice, nome in enumerate(tabella["intestazioni"]):
        valori = [riga[indice] for riga in tabella["righe"]]
        scelta = scelte[indice] if indice < len(scelte) else {}
        analisi = personalizza_colonna(nome, valori, tabella["separatore"], scelta)
        analisi["separatore"] = tabella["separatore"]
        colonne.append(analisi)

    applica_confronto_globale(colonne)
    trasformate = [
        [trasforma_valore(valore, colonne[indice]) for indice, valore in enumerate(riga)]
        for riga in tabella["righe"]
    ]
    riepilogo = {
        "istanze": len(tabella["righe"]),
        "feature": len(tabella["intestazioni"]),
        "numeriche": sum(colonna["tipo"] in ("numerica", "numerica_costante") for colonna in colonne),
        "binarie": sum(colonna["tipo"] == "binaria" for colonna in colonne),
        "nonNumeriche": sum(colonna["tipo"] == "non_numerica" for colonna in colonne),
        "mancanti": sum(colonna["mancanti"] for colonna in colonne),
    }
    return {
        "originale": tabella,
        "colonne": colonne,
        "trasformate": trasformate,
        "riepilogo": riepilogo,
    }


def _valore_csv(valore: Any) -> Any:
    if valore is None:
        return ""
    if isinstance(valore, (int, float)) and not isinstance(valore, bool):
        pulito = 0 if abs(float(valore)) < 1e-14 else float(valore)
        return format(pulito, ".12g")
    return str(valore)


def crea_csv(intestazioni: list[str], righe: list[list[Any]]) -> str:
    destinazione = io.StringIO(newline="")
    scrittore = csv.writer(destinazione, delimiter=",", lineterminator="\n")
    for riga in [intestazioni, *righe]:
        scrittore.writerow([_valore_csv(valore) for valore in riga])
    return destinazione.getvalue().rstrip("\n")


def analizza_csv_json(testo: str, scelte_json: str = "[]") -> str:
    try:
        scelte = json.loads(scelte_json or "[]")
        risultato = prepara_tabella(leggi_csv(testo), scelte)
        return json.dumps({"ok": True, "risultato": risultato}, ensure_ascii=False, separators=(",", ":"))
    except (ValueError, TypeError, json.JSONDecodeError) as errore:
        return json.dumps({"ok": False, "errore": str(errore)}, ensure_ascii=False, separators=(",", ":"))


def crea_csv_json(intestazioni_json: str, righe_json: str) -> str:
    try:
        intestazioni = json.loads(intestazioni_json)
        righe = json.loads(righe_json)
        return json.dumps(
            {"ok": True, "csv": crea_csv(intestazioni, righe)},
            ensure_ascii=False,
            separators=(",", ":"),
        )
    except (ValueError, TypeError, json.JSONDecodeError) as errore:
        return json.dumps({"ok": False, "errore": str(errore)}, ensure_ascii=False, separators=(",", ":"))
