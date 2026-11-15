"""Analisi e riscalamento di tabelle CSV eseguiti interamente in Python."""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import io
import json
import math
import re
from typing import Any


MANCANTI = {"", "na", "n/a", "null", "?"}
INVALIDO = object()
ASSENZA_GOWER = object()  # Categoria assenza esplicitamente confermata; non equivale a un mancante.
NUMERO_PUNTO = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")
NUMERO_VIRGOLA = re.compile(r"^[+-]?(?:\d+(?:,\d*)?|,\d+)(?:[eE][+-]?\d+)?$")

PAROLE_IDENTIFICATIVO = {
    "id", "identificativo", "codice", "code", "key", "chiave", "uuid",
    "matricola", "numero pratica", "numero_pratica", "record id", "record_id",
}
PAROLE_DATA = {"data", "date", "giorno", "mese", "anno", "timestamp", "ora", "time"}
PAROLE_PRESENZA = {
    "presente", "presenza", "assenza", "attivo", "abilitato", "disponibile",
    "has", "is", "flag", "yes", "no", "si",
}
PAROLE_LIVELLO = {"livello", "grado", "rating", "score", "punteggio", "rank", "ordine"}


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




STATI_MANCANTI = {"sconosciuto", "non_applicabile", "assenza"}


def _stato_mancante_dichiarato(
    valore: Any, nome: str, interpretazione: dict[str, Any],
) -> str | None:
    """Significato distinto del singolo marcatore, soltanto in modalità mista.

    Non deduce che 'NA' significhi non applicabile: può essere ignoto,
    non applicabile oppure assenza, ma serve una scelta esplicita.
    """
    if not mancante(valore) or interpretazione.get("significatoMancanti") != "misto":
        return None
    configurazioni = interpretazione.get("statiMancantiPerColonna") or {}
    if not isinstance(configurazioni, dict):
        raise ValueError("La codifica dei marcatori mancanti non è valida.")
    configurazione = configurazioni.get(nome, {})
    if not isinstance(configurazione, dict):
        raise ValueError(f"Configura i marcatori mancanti della colonna “{nome}”.")
    marcatore = str(valore).strip().casefold()
    stato = configurazione.get(marcatore)
    if stato not in STATI_MANCANTI:
        rappresentazione = "(cella vuota)" if marcatore == "" else repr(str(valore).strip())
        raise ValueError(
            f"Per “{nome}”, specifica il significato di {rappresentazione}: "
            "sconosciuto, non applicabile oppure assenza osservata."
        )
    return stato


def _diagnostica_stati_mancanti(
    risultato: dict[str, Any],
    interpretazione: dict[str, Any],
    colonne: list[str],
    ruoli: dict[str, str],
    assegnazioni: dict[str, str],
    gruppi: dict[str, dict[str, Any]],
    percorsi: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[str]]:
    """Verifica le decisioni senza modificare i dati originali del CSV."""
    if interpretazione.get("significatoMancanti") != "misto":
        return {"attiva": False}, []
    intestazioni = risultato["originale"]["intestazioni"]
    righe = risultato["originale"]["righe"]
    indici = {nome: intestazioni.index(nome) for nome in colonne}
    sintesi: dict[str, dict[str, Any]] = {}
    avvisi: list[str] = []
    for nome in colonne:
        conteggi = {"sconosciuto": 0, "non_applicabile": 0, "assenza": 0}
        marcatori: dict[str, int] = {}
        for riga in righe:
            valore = riga[indici[nome]]
            if not mancante(valore):
                continue
            marcatore = str(valore).strip().casefold()
            marcatori[marcatore] = marcatori.get(marcatore, 0) + 1
            try:
                stato = _stato_mancante_dichiarato(valore, nome, interpretazione)
            except ValueError as errore:
                if str(errore) not in avvisi:
                    avvisi.append(str(errore))
                continue
            conteggi[stato] += 1
        if not marcatori:
            continue
        ruolo = ruoli[nome]
        gruppo = gruppi.get(assegnazioni.get(nome), {})
        e_binario = gruppo.get("tipo") == "vettore_binario"
        if conteggi["assenza"] and ruolo not in {"presenza", "binaria", "categoria"}:
            avvisi.append(
                f"Per “{nome}”, un'assenza può essere uno stato osservato soltanto "
                "per categorie o variabili binarie. Per quantità, livelli, testi e "
                "tempi devi scegliere un trattamento specifico, senza sostituire "
                "l'assenza con zero automaticamente."
            )
        if conteggi["assenza"] and gruppo and not e_binario:
            avvisi.append(
                f"Per “{nome}”, le assenze osservate non sono supportate "
                f"nel gruppo “{gruppo.get('nome', gruppo.get('id'))}”. "
                "Modifica il ruolo o il blocco."
            )
        sintesi[nome] = {"marcatori": marcatori, "conteggi": conteggi}
    # Le politiche che trasformerebbero non-applicabilità e valori
    # ignoti in zeri o strutture vuote sono incompatibili.
    for percorso in percorsi:
        mancanti = percorso.get("mancanti", {})
        nomi = percorso["colonne"]
        presenza_esclusa = any(
            sintesi.get(nome, {}).get("conteggi", {}).get("sconosciuto", 0)
            + sintesi.get(nome, {}).get("conteggi", {}).get("non_applicabile", 0) > 0
            for nome in nomi
        )
        if not presenza_esclusa:
            continue
        strategia = mancanti.get("strategia")
        incompatibile = (
            (percorso["tipo"] == "gruppo"
             and strategia == "zero")
            or (percorso["tipo"] == "separato"
                and strategia in {"stringa_vuota", "insieme_vuoto"})
            or (percorso["tipo"] == "numerico" and
                any(
                    v == "zero" for k, v in mancanti.get("perColonna", {}).items()
                    if sintesi.get(k, {}).get("conteggi", {}).get("sconosciuto", 0)
                    + sintesi.get(k, {}).get("conteggi", {}).get("non_applicabile", 0) > 0
                ))
        )
        if incompatibile:
            avvisi.append(
                f"Il percorso “{percorso['titolo']}” convertirebbe un valore "
                "sconosciuto o non applicabile in zero o in una struttura "
                "vuota. Cambia la politica: i significati confermati "
                "per simbolo prevalgono sulle sostituzioni generiche."
            )
        if percorso["tipo"] in {"numerico", "gruppo"}:
            for nome in nomi:
                if sintesi.get(nome, {}).get("conteggi", {}).get("non_applicabile", 0) == 0:
                    continue
                strategia_colonna = (
                    mancanti.get("perColonna", {}).get(nome)
                    if percorso["tipo"] == "numerico" else strategia
                )
                if strategia_colonna in {"imputa_media", "imputa_mediana", "interpola_lineare"}:
                    avvisi.append(
                        f"Per “{nome}” non imputare o interpolare automaticamente un "
                        "valore non applicabile. Escludi il suo contributo oppure "
                        "usa soltanto le coordinate osservate, se la misura lo consente."
                    )
    return {
        "attiva": True, "perColonna": sintesi,
        "totali": {
            stato: sum(v["conteggi"][stato] for v in sintesi.values())
            for stato in sorted(STATI_MANCANTI)
        },
        "descrizione": (
            "I marcatori sono interpretati per colonna: sconosciuto e "
            "non applicabile non forniscono contributo osservato; "
            "l'assenza è uno stato reale soltanto nei percorsi compatibili. "
            "L'identico simbolo non può avere due significati diversi "
            "nella stessa colonna."
        ),
    }, avvisi

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
    # Indice di Bowley, in [-1,1], robusto rispetto alle code estreme.
    # Un IQR nullo non autorizza a imputare una asimmetria pari a zero.
    bowley = (q3 + q1 - 2 * mediana) / iqr if iqr > 0 else None
    return {
        "asimmetriaBowley": bowley,
        "numeroOsservati": len(valori),
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
            if metodo == "log" and stats["minimo"] <= 0:
                raise ValueError(
                    f"La trasformazione log(x) per “{nome}” richiede "
                    "tutti i valori osservati strettamente positivi (x>0). "
                    "Nessuno zero o numero negativo viene traslato automaticamente: "
                    "scegli log(1+x) solo se semanticamente appropriato, "
                    "oppure modifica la trasformazione."
                )
            if metodo == "log1p" and stats["minimo"] < 0:
                raise ValueError(
                    f"La trasformazione log(1+x) per “{nome}” e' disponibile "
                    "solo con valori osservati maggiori o uguali a zero. "
                    "Scegli un'altra trasformazione o rivedi il significato dei dati."
                )
            motivi = {
                "zscore": "Non emergono outlier rilevanti." if metodo_scelto == "auto" else "Le differenze vengono riportate su una scala comune.",
                "robusto": descrivi_outlier(stats) if metodo_scelto == "auto" else "Viene ridotto il peso degli outlier.",
                "maxabs": "Molti valori sono uguali a zero." if metodo_scelto == "auto" else "Gli zeri restano invariati.",
                "minmax": "I valori vengono riportati tra 0 e 1.",
                "log": (
                    "Trasformazione log(x) scelta esplicitamente sui valori "
                    "strettamente positivi: la differenza assoluta trasformata "
                    "è |log(x/y)|, quindi confronta rapporti anziché scarti "
                    "assoluti. Le unità di misura devono essere coerenti; "
                    "non si aggiunge alcuna costante agli input."
                ),
                "log1p": (
                    "Trasformazione log(1+x) scelta esplicitamente: preserva zero "
                    "e comprime gli scarti grandi. Richiede valori non negativi "
                    "e modifica il significato delle differenze."
                ),
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
        else:
            colonna["motivo"] = (
                "Le quantità vengono standardizzate automaticamente, anche quando le "
                "dispersioni osservate sono simili."
                if rapporto <= 2 else
                "Le feature numeriche hanno dispersioni molto diverse."
            )


def _parole_nome(nome: str) -> set[str]:
    pulito = re.sub(r"[^\w]+", " ", nome.casefold(), flags=re.UNICODE).strip()
    parole = set(pulito.split())
    parole.add(nome.casefold().strip())
    return parole


def _sembra_data(valore: str) -> bool:
    testo = valore.strip()
    if not testo:
        return False
    candidati = (
        "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d",
        "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M",
    )
    for formato in candidati:
        try:
            dt.datetime.strptime(testo, formato)
            return True
        except ValueError:
            pass
    return False


def prepara_questionario(tabella: dict[str, Any], colonne: list[dict[str, Any]]) -> dict[str, Any]:
    """Crea ipotesi prudenti e decide quali domande semantiche mostrare."""
    profili: list[dict[str, Any]] = []
    for indice, colonna in enumerate(colonne):
        grezzi = [riga[indice] for riga in tabella["righe"]]
        osservati = [str(v).strip() for v in grezzi if not mancante(v)]
        distinti = len({v.casefold() for v in osservati})
        parole = _parole_nome(colonna["nome"])
        nome_identificativo = bool(parole & PAROLE_IDENTIFICATIVO)
        nome_data = bool(parole & PAROLE_DATA)
        quota_date = sum(_sembra_data(v) for v in osservati) / len(osservati) if osservati else 0
        if nome_identificativo:
            ruolo, motivo = "identificativo", "Il titolo della colonna fa pensare a un codice identificativo."
        elif nome_data or quota_date >= 0.8:
            ruolo, motivo = "data", "Il titolo o i valori fanno pensare a date o orari."
        elif colonna["tipo"] == "binaria":
            ruolo = "presenza" if parole & PAROLE_PRESENZA else "binaria"
            motivo = "La colonna contiene soltanto due valori, 0 e 1."
        elif colonna["tipo"] == "non_numerica" and distinti == 2 and (
            {v.casefold() for v in osservati}
            <= {"si", "sì", "yes", "true", "vero", "presente", "attivo",
                "no", "false", "falso", "assente", "inattivo"}
        ) and any(
            v.casefold() in {"si", "sì", "yes", "true", "vero", "presente", "attivo"}
            for v in osservati
        ) and any(
            v.casefold() in {"no", "false", "falso", "assente", "inattivo"}
            for v in osservati
        ):
            ruolo = "presenza" if parole & PAROLE_PRESENZA else "binaria"
            motivo = "Sono stati riconosciuti due stati testuali come sì/no o vero/falso."
        elif colonna["tipo"] == "non_numerica" and distinti <= min(12, max(4, round(len(osservati) * 0.25))):
            ruolo, motivo = "categoria", "Poche etichette si ripetono in molte righe."
        elif colonna["tipo"] == "non_numerica":
            ruolo, motivo = "testo", "La colonna contiene molte scritte differenti."
        elif colonna["tipo"] == "numerica" and bool(parole & PAROLE_LIVELLO):
            ruolo, motivo = "livello", "Il titolo della colonna fa pensare a livelli ordinati."
        else:
            ruolo, motivo = "quantita", "La colonna contiene valori numerici."

        esclusa = ruolo in {"identificativo", "data", "testo"}
        profili.append({
            "nome": colonna["nome"],
            "ruoloSuggerito": ruolo,
            "motivo": motivo,
            "usaNelConfronto": not esclusa,
            "distinti": distinti,
            "mancanti": colonna["mancanti"],
        })

    return {
        "colonne": profili,
        "condizioni": {
            "mancanti": any(c["mancanti"] > 0 for c in colonne),
            "estremi": any(c.get("statistiche", {}).get("estremi", 0) > 0 for c in colonne),
            "binarie": any(p["ruoloSuggerito"] in {"binaria", "presenza"} for p in profili),
            "livelli": any(p["ruoloSuggerito"] == "livello" for p in profili),
            "date": any(p["ruoloSuggerito"] == "data" for p in profili),
            "numeriche": sum(c["tipo"] in {"numerica", "numerica_costante"} for c in colonne) >= 2,
        },
    }


def trasforma_valore(valore: Any, analisi: dict[str, Any]) -> Any:
    """Unica trasformazione numerica, condivisa con il calcolo delle distanze."""
    if analisi["tipo"] == "non_numerica":
        return None if mancante(valore) else valore
    return _trasforma_per_percorso(valore, analisi, analisi["metodo"])


def prepara_tabella(tabella: dict[str, Any], scelte: list[dict[str, str]] | None = None) -> dict[str, Any]:
    scelte = scelte or []
    colonne: list[dict[str, Any]] = []
    for indice, nome in enumerate(tabella["intestazioni"]):
        valori = [riga[indice] for riga in tabella["righe"]]
        scelta = scelte[indice] if indice < len(scelte) else {}
        analisi = personalizza_colonna(nome, valori, tabella["separatore"], scelta)
        analisi["separatore"] = tabella["separatore"]
        colonne.append(analisi)

    # Le proposte preliminari sono per-colonna: feature escluse dal
    # confronto non devono condizionare la trasformazione di quelle incluse.
    # La diagnosi multivariata è costruita dopo la selezione delle feature.
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
        "questionario": prepara_questionario(tabella, colonne),
    }


ETICHETTE_RUOLO = {
    "quantita": "Quantità misurata", "livello": "Livello ordinato",
    "presenza": "Presenza o assenza", "binaria": "Risposta con due possibilità",
    "categoria": "Categoria senza ordine", "identificativo": "Codice identificativo",
    "data": "Data o orario", "testo": "Testo o sequenza",
    "insieme": "Insieme di etichette", "ciclica": "Grandezza ciclica",
    "risultato": "Risultato da spiegare o prevedere",
    "altro": "Significato da specificare", "ignoto": "Significato non ancora noto",
}


def _blocco_indipendente(nome: str, ruolo: str, analisi: dict[str, Any], interpretazione: dict[str, Any]) -> dict[str, Any]:
    """Traduce una caratteristica indipendente in una regola di confronto."""
    tipo = analisi["tipo"]
    avvisi: list[str] = []
    stato = "pronto"

    if ruolo == "quantita":
        if tipo not in {"numerica", "numerica_costante"}:
            misura, motivo = "Da decidere", "Una quantità deve contenere valori numerici."
            avvisi.append("Controlla il significato o il tipo di dato della colonna.")
            stato = "da_completare"
        else:
            misura = "Differenza numerica"
            motivo = "Confronta quanto sono lontani i valori dopo averli riportati su una scala comune."
    elif ruolo == "livello":
        risposta = interpretazione.get("ordinePerColonna", {}).get(
            nome, interpretazione.get("ordineLivelli", "")
        )
        if risposta == "no":
            misura, motivo = "Uguale o diverso", "I livelli sono trattati come etichette perché l’ordine non ha significato."
        elif risposta == "si" and tipo == "non_numerica":
            if interpretazione.get("ordiniLivelliGower", {}).get(nome, "").strip():
                misura, motivo = "Differenza tra ranghi normalizzata", "Usa l’ordine esplicitamente indicato per i livelli testuali."
            else:
                misura, motivo = "Da decidere", "Per i livelli testuali occorre specificare l’ordine delle etichette."
                avvisi.append("Indica l’ordine dei livelli testuali, separandoli con punto e virgola.")
                stato = "da_completare"
        elif risposta == "si":
            misura, motivo = "Differenza tra ranghi normalizzata", "Tiene conto dell’ordine dei livelli e non della distanza numerica grezza."
        else:
            misura, motivo = "Da decidere", "Occorre sapere se l’ordine dei livelli ha significato."
            avvisi.append("Rispondi alla domanda sull’ordine dei livelli.")
            stato = "da_completare"
    elif ruolo == "presenza":
        if tipo not in {"binaria", "non_numerica", "numerica_costante"}:
            misura, motivo = "Da decidere", "Una presenza o assenza deve avere al massimo due stati distinti."
            avvisi.append("Controlla il significato o il tipo di dato della colonna.")
            stato = "da_completare"
        else:
            risposta = interpretazione.get("zeriCondivisiPerColonna", {}).get(
                nome, interpretazione.get("zeriCondivisi", "")
            )
            if risposta == "si":
                misura, motivo = "Disaccordo binario", "Sia le presenze sia le assenze condivise contribuiscono alla somiglianza."
            elif risposta == "no":
                misura, motivo = "Confronto asimmetrico di Jaccard", "Le assenze condivise vengono ignorate; contano soprattutto le presenze."
            else:
                misura, motivo = "Da decidere", "Occorre sapere se due assenze condivise debbano contare come somiglianza."
                avvisi.append("Rispondi alla domanda sulle assenze condivise.")
                stato = "da_completare"
    elif ruolo == "binaria":
        if tipo not in {"binaria", "non_numerica", "numerica_costante"}:
            misura, motivo = "Da decidere", "Una risposta binaria deve contenere al massimo due stati."
            avvisi.append("Controlla il significato o il tipo di dato della colonna.")
            stato = "da_completare"
        else:
            misura, motivo = "Disaccordo binario", "Due risposte uguali hanno contributo 0; due risposte diverse hanno contributo 1."
    elif ruolo in {"categoria", "identificativo"}:
        misura, motivo = "Uguale o diverso", "Confronta le etichette senza introdurre un ordine artificiale."
        if ruolo == "identificativo":
            avvisi.append("Un identificativo di solito serve a nominare le righe e non a confrontarle.")
            stato = "attenzione"
    elif ruolo == "data":
        risposta = interpretazione.get("usoDate", "")
        if risposta in {"vicinanza", "durata"}:
            misura, motivo = "Differenza temporale", "Confronta il tempo che separa le due date."
        elif risposta == "ordine":
            misura, motivo = "Differenza tra posizioni temporali", "Conta l’ordine cronologico, non la distanza temporale assoluta."
        elif risposta == "escludi":
            misura, motivo = "Da escludere", "Hai indicato che le date non devono influire sul confronto."
            avvisi.append("Disattiva questa colonna nel confronto.")
            stato = "da_completare"
        else:
            misura, motivo = "Da decidere", "Occorre stabilire come le date debbano contribuire al confronto."
            avvisi.append("Rispondi alla domanda sull’uso delle date.")
            stato = "da_completare"
    elif ruolo == "insieme":
        configurata = interpretazione.get("configurazioniInsiemi") or {}
        specifica = configurata.get(nome, {}) if isinstance(configurata, dict) else {}
        if not isinstance(specifica, dict):
            specifica = {}
        scelta = specifica.get("misura")
        if tipo != "non_numerica":
            misura, motivo = "Da decidere", "Per gli insiemi servono celle con etichette, non quantità."
            avvisi.append("Controlla il tipo di dato: imposta la colonna come non numerica.")
            stato = "da_completare"
        elif (specifica.get("conferma") != "si"
              or specifica.get("separatore") not in {"|", ";", ","}
              or specifica.get("maiuscole") not in {"distingui", "ignora"}
              or specifica.get("ripetizioni") != "deduplica"
              or scelta not in {"jaccard", "dice"}):
            misura, motivo = "Da decidere", (
                "Una cella può descrivere un insieme solo se confermi separatore, "
                "trattamento delle etichette, ripetizioni e formula."
            )
            avvisi.append(
                "Conferma la struttura insiemistica, il separatore, le maiuscole, "
                "le ripetizioni e scegli Jaccard oppure Dice."
            )
            stato = "da_completare"
        else:
            misura = ("Dissimilarità di Jaccard tra insiemi" if scelta == "jaccard"
                      else "Dissimilarità di Dice tra insiemi")
            motivo = (
                "Confronta le etichette come insiemi, indipendentemente dall'ordine. "
                "Le ripetizioni sono ignorate; [] indica un insieme vuoto osservato. "
                "Jaccard e Dice valgono zero per due insiemi entrambi vuoti."
            )
    elif ruolo == "ciclica":
        opzioni = interpretazione.get("configurazioniCicliche") or {}
        specifica = opzioni.get(nome, {}) if isinstance(opzioni, dict) else {}
        if not isinstance(specifica, dict):
            specifica = {}
        try:
            periodo = float(str(specifica.get("periodo", "")).strip().replace(",", "."))
        except (ValueError, TypeError):
            periodo = math.nan
        if tipo not in {"numerica", "numerica_costante", "binaria"}:
            misura, motivo = "Da decidere", "La distanza ciclica richiede numeri."
            avvisi.append("La colonna deve essere numerica; verifica il tipo rilevato.")
            stato = "da_completare"
        elif (not math.isfinite(periodo) or periodo <= 0
              or specifica.get("unita") not in {"ore", "giorni", "gradi", "radianti", "altre"}):
            misura, motivo = "Da decidere", "Per il ciclo occorrono un periodo positivo e un'unità dichiarati."
            avvisi.append(
                "Indica il periodo P > 0 e le unità di misura. "
                "I valori devono rappresentare posizioni in [0,P)."
            )
            stato = "da_completare"
        else:
            misura = "Distanza ciclica normalizzata"
            motivo = (
                f"Periodo dichiarato P={format(periodo,'.10g')} "
                f"({specifica['unita']}); confronta l'arco più corto sul ciclo, "
                "con risultato in [0,1]. I valori originali non vengono riscalati."
            )
    elif ruolo == "testo":
        preferenze = interpretazione.get("misureTestualiPerColonna") or {}
        if not isinstance(preferenze, dict):
            raise ValueError("La scelta delle misure testuali non e' valida.")
        scelta = preferenze.get(nome, "levenshtein")
        if scelta == "levenshtein":
            misura = "Distanza di Levenshtein normalizzata"
            motivo = (
                "Confronta inserimenti, cancellazioni e sostituzioni, "
                "anche tra sequenze di lunghezze differenti."
            )
        elif scelta == "hamming":
            misura = "Distanza di Hamming normalizzata"
            motivo = (
                "Conta le posizioni con simboli differenti, divise per la "
                "lunghezza comune. Richiede sequenze allineate ed equidimensionali."
            )
        elif scelta == "damerau_levenshtein":
            misura = "Distanza di Damerau–Levenshtein normalizzata"
            motivo = (
                "Confronta inserimenti, cancellazioni, sostituzioni e trasposizioni "
                "adiacenti con costo unitario; divide per la lunghezza massima "
                "per ottenere un contributo in [0,1]. Non e' la distanza grezza."
            )
        else:
            misura = "Da decidere"
            motivo = "La misura testuale indicata non e' riconosciuta."
            avvisi.append("Scegli Levenshtein, Damerau–Levenshtein oppure Hamming per questa colonna.")
            stato = "da_completare"
    elif ruolo == "risultato":
        misura = "Da decidere"
        motivo = "Un risultato da spiegare o prevedere normalmente non deve definire la somiglianza tra le righe."
        avvisi.append("Valuta se questa colonna debba essere esclusa dal confronto.")
        stato = "da_completare"
    else:
        misura, motivo = "Da decidere", "Il significato della colonna non è ancora sufficiente per scegliere una misura."
        avvisi.append("Specifica meglio che cosa rappresenta la colonna.")
        stato = "da_completare"

    if tipo == "numerica_costante" and stato == "pronto":
        avvisi.append("La colonna è costante e non distingue nessuna coppia di righe.")
        stato = "attenzione"

    return {"nome": nome, "colonne": [nome], "interpretazione": ETICHETTE_RUOLO.get(ruolo, ruolo),
            "misura": misura, "motivo": motivo, "stato": stato, "avvisi": avvisi}


def _blocco_gruppo(gruppo: dict[str, Any], membri: list[str], analisi_per_nome: dict[str, dict[str, Any]], interpretazione: dict[str, Any], ruoli: dict[str, str]) -> dict[str, Any]:
    """Traduce un gruppo di colonne in una sola regola di confronto."""
    nome = str(gruppo.get("nome") or "Gruppo senza nome")
    tipo_gruppo = gruppo.get("tipo", "altro")
    avvisi: list[str] = []
    stato = "pronto"
    etichetta = {"ripetute": "Misurazioni dello stesso profilo", "tempo": "Osservazioni successive nel tempo",
                 "parti": "Parti dello stesso totale", "coordinate": "Coordinate quantitative da confrontare insieme",
                 "distribuzione": "Distribuzioni di probabilità o istogrammi",
                 "vettore_binario": "Vettore di presenze e assenze",
                 "tempo_coppie": "Serie con timestamp diversi per ogni riga",
                 "altro": "Gruppo di caratteristiche"}.get(tipo_gruppo, "Gruppo di caratteristiche")
    id_gruppo = str(gruppo.get("id", ""))
    id_misura: str | None = None
    parametri: dict[str, Any] = {}

    if len(membri) < (4 if tipo_gruppo == "tempo_coppie" else 2):
        misura, motivo = "Da completare", (
            "Una serie con coppie tempo-valore richiede almeno due coppie, cioè quattro colonne."
            if tipo_gruppo == "tempo_coppie" else
            "Un gruppo deve contenere almeno due colonne."
        )
        avvisi.append("Assegna almeno due colonne al gruppo oppure rimuovilo.")
        stato = "da_completare"
    else:
        tipi = {analisi_per_nome[m]["tipo"] for m in membri if m in analisi_per_nome}
        numerico = bool(tipi) and tipi <= {"numerica", "numerica_costante"}
        # Masse con soli 0 e 1 sono frequenti negli istogrammi; il
        # riconoscimento automatico come binaria non deve impedire la
        # successiva interpretazione esplicita come probabilità.
        numerico_distribuzione = bool(tipi) and tipi <= {
            "numerica", "numerica_costante", "binaria"
        }
        quantitativo = (
            (numerico_distribuzione if tipo_gruppo in {"distribuzione", "tempo_coppie"} else numerico)
            and all(ruoli.get(m) == "quantita" for m in membri)
        )
        binario = (
            tipo_gruppo == "vettore_binario"
            and tipi <= {"binaria", "numerica_costante", "non_numerica"}
            and all(ruoli.get(m) in {"binaria", "presenza"} for m in membri)
        )
        if tipo_gruppo in {"ripetute", "tempo", "parti", "coordinate", "distribuzione", "tempo_coppie"} and not quantitativo:
            misura, motivo = "Da decidere", "Questa struttura richiede quantità numeriche, non codici o livelli ordinali."
            avvisi.append("Controlla il significato e il tipo delle colonne del gruppo.")
            stato = "da_completare"
        elif tipo_gruppo == "vettore_binario":
            scelte_binarie = {
                "hamming": "Distanza di Hamming binaria normalizzata",
                "rogers_tanimoto": "Dissimilarità di Rogers–Tanimoto",
                "jaccard": "Dissimilarità di Jaccard binaria",
                "dice": "Dissimilarità di Dice",
            }
            scelta_binaria = interpretazione.get(f"misuraBinaria-{id_gruppo}", "")
            if not binario:
                misura, motivo = "Da decidere", (
                    "Servono almeno due colonne di presenze o risposte binarie, "
                    "ognuna con stati interpretabili come 0 e 1."
                )
                avvisi.append(
                    "Per un vettore binario assegna ruoli presenza/binaria a tutte "
                    "le colonne e controlla che contengano 0/1 o sì/no."
                )
                stato = "da_completare"
            elif scelta_binaria not in scelte_binarie:
                misura, motivo = "Da decidere", (
                    "La scelta dei disaccordi, delle assenze comuni e delle "
                    "presenze comuni determina la misura binaria del gruppo."
                )
                avvisi.append(
                    "Scegli Hamming, Rogers–Tanimoto, Jaccard oppure Dice "
                    "per il vettore di presenze."
                )
                stato = "da_completare"
            else:
                id_misura = scelta_binaria
                misura = scelte_binarie[id_misura]
                motivo = {
                    "hamming": "Quota di caratteristiche binarie discordanti; le assenze comuni contano.",
                    "rogers_tanimoto": "Penalizza i disaccordi due volte rispetto agli accordi, comprese le doppie assenze.",
                    "jaccard": "Considera le co-presenze e i disaccordi, ignorando le assenze comuni; due vettori nulli hanno dissimilarità zero per convenzione.",
                    "dice": "Dà doppio peso alle co-presenze e ignora le assenze comuni; non è definita per un vettore nullo confrontato con se stesso.",
                }[id_misura]
        elif tipo_gruppo == "tempo_coppie":
            # Timestamp e numero dei campioni sono propri di ogni singola riga.
            allineamenti = interpretazione.get("metodiAllineamentoTemporaleGruppi") or {}
            scelta = allineamenti.get(id_gruppo, "") if isinstance(allineamenti, dict) else ""
            if scelta == "dtw":
                misura = "Dynamic Time Warping"
                id_misura = "dtw_eventi"
                motivo = (
                    "Ogni oggetto è una sequenza di coppie (tempo, valore). "
                    "La DTW minimizza il costo medio effettivo del cammino; "
                    "i timestamp entrano nel costo solo con penalità confermata."
                )
            elif scelta == "lcss":
                misura = "Dissimilarità LCSS normalizzata"
                id_misura = "lcss_eventi"
                motivo = (
                    "Ogni oggetto ha la propria sequenza cronologica; LCSS "
                    "richiede tolleranze dichiarate su valori e timestamp fisici."
                )
            else:
                misura, motivo = "Da decidere", (
                    "Scegli DTW oppure LCSS; punto-a-punto e pendenze "
                    "richiederebbero una griglia comune o interpolazione esplicita."
                )
                avvisi.append("Scegli DTW oppure LCSS per le serie a tempi per riga.")
                stato = "da_completare"
        elif tipo_gruppo == "coordinate":
            misura, motivo = "Da decidere", (
                "Scegli esplicitamente la misura per questo gruppo di coordinate quantitative."
            )
            stato = "da_completare"
        elif tipo_gruppo == "ripetute":
            risposta = interpretazione.get(f"somiglianza-{gruppo.get('id')}", "")
            scelte = {
                "valori_vicini": ("Distanza tra coordinate", "Confronta i valori coordinata per coordinata e riassume il gruppo in un solo contributo."),
                "proporzioni": ("Dissimilarità coseno", "Confronta la direzione dei profili, riducendo l’effetto della loro grandezza complessiva."),
                "andamento": ("Dissimilarità di Pearson", "Confronta come i valori crescono e diminuiscono rispetto al livello medio del profilo."),
                "ordine": ("Dissimilarità di Spearman", "Confronta l’ordinamento interno delle coordinate dei due profili."),
                "ordine_coppie": (
                    "Dissimilarità di Kendall τ-b",
                    "Confronta la concordanza dell'ordine di ogni coppia di caratteristiche, "
                    "tenendo conto dei pari merito con Kendall τ-b."
                ),
            }
            if risposta in scelte:
                misura, motivo = scelte[risposta]
            else:
                misura, motivo = "Da decidere", "Occorre stabilire quale aspetto del profilo debba definire la somiglianza."
                avvisi.append(f"Rispondi alla domanda sul gruppo “{nome}”.")
                stato = "da_completare"
        elif tipo_gruppo == "tempo":
            risposta = interpretazione.get(f"ritardo-{gruppo.get('id')}", "")
            if risposta == "si":
                modi = interpretazione.get("metodiAllineamentoTemporaleGruppi") or {}
                scelta_allineamento = modi.get(id_gruppo, "dtw") if isinstance(modi, dict) else ""
                if scelta_allineamento == "dtw":
                    misura, motivo = "Dynamic Time Warping", (
                        "Confronta cammini monotoni a costo medio minimo esatto; "
                        "un eventuale scarto fra timestamp richiede un costo temporale dichiarato."
                    )
                elif scelta_allineamento == "lcss":
                    misura, motivo = "Dissimilarità LCSS normalizzata", (
                        "Conta gli eventi simili che possono essere allineati in ordine "
                        "entro tolleranze dichiarate su valore e tempo."
                    )
                else:
                    misura, motivo = "Da decidere", "Scegli DTW oppure LCSS."
                    stato = "da_completare"
                    avvisi.append("Scegli la modalità di allineamento temporale.")
            elif risposta == "no":
                modi = interpretazione.get("misureTemporaliGruppi") or {}
                scelta_temporale = modi.get(id_gruppo, "punto") if isinstance(modi, dict) else ""
                if scelta_temporale == "punto":
                    misura, motivo = "Distanza punto per punto", (
                        "Confronta osservazioni che corrispondono agli stessi istanti condivisi."
                    )
                elif scelta_temporale == "pendenze":
                    misura, motivo = "Distanza sulle pendenze", (
                        "Confronta variazioni divise per gli intervalli fisici tra istanti: "
                        "due serie che differiscono per una costante additiva hanno distanza zero."
                    )
                else:
                    misura, motivo = "Da decidere", "Scegli confronto punto per punto oppure sulle pendenze."
                    avvisi.append("Scegli la misura temporale senza allineamento.")
                    stato = "da_completare"
            else:
                misura, motivo = "Da decidere", "Occorre sapere se piccoli ritardi temporali debbano essere tollerati."
                avvisi.append(f"Rispondi alla domanda sul ritardo nel gruppo “{nome}”.")
                stato = "da_completare"
        elif tipo_gruppo == "distribuzione":
            natura = interpretazione.get(f"naturaDistribuzione-{id_gruppo}", "")
            scelta_distribuzione = interpretazione.get(f"misuraDistribuzione-{id_gruppo}", "")
            titoli = {
                "hellinger": "Distanza di Hellinger",
                "jensen_shannon": "Distanza di Jensen–Shannon",
            }
            misura = titoli.get(scelta_distribuzione, "Da decidere")
            motivo = (
                "Confronta le masse delle stesse categorie o intervalli "
                "con un'unica distribuzione per riga. Non confronta i rapporti "
                "tra parti secondo la geometria di Aitchison."
            )
            if natura not in {"probabilita", "masse"}:
                avvisi.append(
                    "Indica se le righe contengono probabilità con somma 1 "
                    "oppure frequenze o masse da dividere per il totale della riga."
                )
                stato = "da_completare"
            if scelta_distribuzione not in titoli:
                avvisi.append("Scegli Hellinger oppure Jensen–Shannon per il gruppo.")
                stato = "da_completare"
            if stato == "pronto":
                id_misura = scelta_distribuzione
                parametri = {"natura": natura}
                motivo += (
                    " Le righe sono controllate come probabilità già normalizzate."
                    if natura == "probabilita" else
                    " Ogni riga è normalizzata per la propria massa totale."
                )
        elif tipo_gruppo == "parti":
            risposta = interpretazione.get(f"totale-{gruppo.get('id')}", "")
            if risposta == "si":
                misura, motivo = "Distanza composizionale di Aitchison", "Confronta le proporzioni tra le parti, non la grandezza totale."
                if any(analisi_per_nome[m].get("statistiche", {}).get("minimo", 0) < 0 for m in membri):
                    avvisi.append("Aitchison richiede componenti strettamente positive: sono presenti valori negativi.")
                    stato = "da_completare"
                ha_zeri = (
                    any(analisi_per_nome[m].get("statistiche", {}).get("zeri", 0) > 0 for m in membri)
                    or interpretazione.get(f"mancanti-gruppo-{gruppo.get('id')}") == "zero"
                )
                if ha_zeri:
                    scelta_zeri = interpretazione.get(f"zeri-aitchison-{gruppo.get('id')}", "")
                    if scelta_zeri == "sostituisci":
                        motivo += (
                            " Gli zeri verranno sostituiti, dopo la chiusura a somma 1, "
                            "con una piccola proporzione positiva che conserva massa per "
                            "le componenti osservate."
                        )
                    elif scelta_zeri == "strutturali":
                        avvisi.append(
                            "Gli zeri indicano assenze reali: la distanza di Aitchison non è adatta. "
                            "Indica che le colonne non devono essere trattate come una composizione."
                        )
                        stato = "da_completare"
                    else:
                        avvisi.append(
                            "Sono presenti zeri: indica se sono valori sotto soglia sostituibili "
                            "oppure assenze reali incompatibili con Aitchison."
                        )
                        stato = "da_completare"
            elif risposta == "no":
                misura, motivo = "Distanza tra coordinate", "Le quantità vengono confrontate insieme, senza trattarle come parti di una composizione."
            else:
                misura, motivo = "Da decidere", "Occorre confermare se le colonne siano realmente parti di un unico totale."
                avvisi.append(f"Rispondi alla domanda sul totale del gruppo “{nome}”.")
                stato = "da_completare"
        else:
            misura, motivo = "Da decidere", "Non è ancora specificato quale relazione unisca le colonne del gruppo."
            avvisi.append("Descrivi il gruppo con una delle interpretazioni disponibili.")
            stato = "da_completare"

        # Le misure dei gruppi sono indipendenti dalla scelta per le colonne
        # quantitative non raggruppate. Non e' permessa una scelta incompatibile
        # con il significato dichiarato del gruppo.
        mappe = interpretazione.get("misureGruppi") or {}
        if not isinstance(mappe, dict):
            raise ValueError("Le misure dei gruppi non sono configurate correttamente.")
        scelta = str(mappe.get(id_gruppo) or "")
        scelte_coordinate = {
            "euclidean": "Distanza euclidea",
            "manhattan": "Distanza di Manhattan",
            "chebyshev": "Distanza di Chebyshev",
            "minkowski": "Distanza di Minkowski",
            "weighted_minkowski": "Distanza di Minkowski pesata",
        }
        confronto_coordinate = (
            tipo_gruppo == "coordinate"
            or (tipo_gruppo == "ripetute" and interpretazione.get(f"somiglianza-{id_gruppo}") == "valori_vicini")
            or (
                tipo_gruppo == "tempo"
                and interpretazione.get(f"ritardo-{id_gruppo}") == "no"
                and (interpretazione.get("misureTemporaliGruppi") or {}).get(id_gruppo, "punto") == "punto"
            )
            or (tipo_gruppo == "parti" and interpretazione.get(f"totale-{id_gruppo}") == "no")
        )
        if scelta and not confronto_coordinate:
            avvisi.append(
                "La misura selezionata non e' compatibile con lo scopo dichiarato "
                "per questo gruppo. Rivedi la scelta o l'interpretazione."
            )
            stato = "da_completare"
        elif confronto_coordinate and quantitativo:
            if not scelta and tipo_gruppo == "coordinate":
                avvisi.append("Scegli una misura per questo gruppo di coordinate.")
            elif scelta and scelta not in scelte_coordinate:
                avvisi.append("La misura del gruppo non e' riconosciuta o non e' compatibile.")
                stato = "da_completare"
            else:
                # Per i profili gia' guidati e le serie sincronizzate si
                # conserva il precedente comportamento euclideo finche'
                # l'utente non indica una misura diversa.
                id_misura = scelta or "euclidean"
                misura = scelte_coordinate[id_misura]
                motivo = (
                    "Confronta gli scarti fra le coordinate del solo gruppo, "
                    "senza usare quelle degli altri blocchi."
                )
                stato = "pronto"
                parametri = {}
                if id_misura in {"minkowski", "weighted_minkowski"}:
                    ordini = interpretazione.get("ordiniGruppi") or {}
                    if not isinstance(ordini, dict):
                        raise ValueError("Gli esponenti dei gruppi non sono validi.")
                    try:
                        q = float(str(ordini.get(id_gruppo, "2")).strip().replace(",", "."))
                    except (TypeError, ValueError):
                        q = math.nan
                    if not math.isfinite(q) or q < 1:
                        avvisi.append("Inserisci per Minkowski un esponente q finito maggiore o uguale a 1.")
                        stato = "da_completare"
                    else:
                        parametri["q"] = q
                if id_misura == "weighted_minkowski":
                    config_pesi = interpretazione.get("pesiGruppi") or {}
                    if not isinstance(config_pesi, dict):
                        raise ValueError("I pesi interni dei gruppi non sono validi.")
                    pesi = _lista_numeri_positivi(
                        config_pesi.get(id_gruppo, "; ".join("1" for _ in membri))
                    )
                    if pesi is None or len(pesi) != len(membri):
                        avvisi.append(
                            f"Servono {len(membri)} pesi strettamente positivi, "
                            "uno per ogni colonna del gruppo."
                        )
                        stato = "da_completare"
                    else:
                        parametri["pesi"] = pesi

    colonne_nell_ordine = list(membri)
    campionamento_temporale: str | None = None
    if tipo_gruppo == "tempo_coppie" and len(membri) >= 4:
        testo_coppie = (interpretazione.get("coppieTemporaliGruppi") or {}).get(id_gruppo, "")
        unita = (interpretazione.get("unitaTemporaleGruppi") or {}).get(id_gruppo, "")
        try:
            coppie = _interpreta_coppie_temporali(testo_coppie, membri)
            parametri["coppie"] = coppie
            colonne_nell_ordine = [colonna for coppia in coppie for colonna in coppia]
        except ValueError as errore:
            stato = "da_completare"
            avvisi.append(str(errore))
        if unita not in {"secondi", "minuti", "ore", "giorni", "altre"}:
            stato = "da_completare"
            avvisi.append("Indica un'unica unità per i timestamp di tutte le righe.")
        else:
            parametri["unitaTempo"] = unita
        parametri["griglia"] = "per_riga"
        if misura == "Dynamic Time Warping":
            costo = (interpretazione.get("costiDTWGruppi") or {}).get(id_gruppo, "")
            if costo not in {"assoluto", "quadratico"}:
                stato = "da_completare"
                avvisi.append("Scegli esplicitamente il costo locale DTW.")
            else:
                parametri["costoLocale"] = costo
            finestra = (interpretazione.get("finestreDTWGruppi") or {}).get(id_gruppo, "")
            if not isinstance(finestra, str) or (
                finestra.strip() and not finestra.strip().isdigit()
            ):
                stato = "da_completare"
                avvisi.append("La finestra DTW deve essere vuota oppure un intero non negativo.")
            elif finestra.strip():
                parametri["finestra"] = int(finestra.strip())
            penalita = (interpretazione.get("penalizzazioniDTWGruppi") or {}).get(id_gruppo, "")
            if penalita not in {"si", "no"}:
                stato = "da_completare"
                avvisi.append("Conferma se DTW deve penalizzare lo sfasamento temporale.")
            elif penalita == "si":
                try:
                    lam = float(str((interpretazione.get("pesiRitardoDTWGruppi") or {}).get(id_gruppo, "")).replace(",", "."))
                    tau = float(str((interpretazione.get("scaleRitardoDTWGruppi") or {}).get(id_gruppo, "")).replace(",", "."))
                except (ValueError, TypeError):
                    lam, tau = math.nan, math.nan
                if not math.isfinite(lam) or lam <= 0:
                    avvisi.append("Per penalizzare lo sfasamento indica λ > 0.")
                    stato = "da_completare"
                elif not math.isfinite(tau) or tau <= 0:
                    avvisi.append("Indica una scala temporale τ > 0 nelle unità dichiarate.")
                    stato = "da_completare"
                else:
                    parametri["lambdaRitardo"] = lam
                    parametri["tauRitardo"] = tau
            else:
                parametri["timestampIgnoratiNelCosto"] = True
                motivo += (
                    " Hai confermato che lo sfasamento fisico non conta nel costo: "
                    "i timestamp servono solo per ordinare i campioni."
                )
        elif misura == "Dissimilarità LCSS normalizzata":
            try:
                eps = float(str((interpretazione.get("tolleranzeValoreLCSSGruppi") or {}).get(id_gruppo, "")).replace(",", "."))
                tol_t = float(str((interpretazione.get("tolleranzeTempoLCSSGruppi") or {}).get(id_gruppo, "")).replace(",", "."))
            except (ValueError, TypeError):
                eps, tol_t = math.nan, math.nan
            if not all(math.isfinite(v) and v >= 0 for v in (eps, tol_t)):
                stato = "da_completare"
                avvisi.append("LCSS richiede tolleranze finite e non negative per valori e tempo.")
            else:
                parametri["tolleranzaValori"] = eps
                parametri["tolleranzaTempo"] = tol_t
    if tipo_gruppo == "tempo" and len(membri) >= 2:
        ordini = interpretazione.get("ordiniTemporaliGruppi") or {}
        campionamenti = interpretazione.get("campionamentiTemporaliGruppi") or {}
        if not isinstance(ordini, dict) or not isinstance(campionamenti, dict):
            raise ValueError("La configurazione temporale per i gruppi non e' valida.")
        ordine_grezzo = ordini.get(id_gruppo, "")
        if not isinstance(ordine_grezzo, str):
            raise ValueError(f"Specifica l'ordine temporale del gruppo “{nome}” come elenco.")
        specificato = [val.strip() for val in ordine_grezzo.split(";")]
        if not ordine_grezzo.strip():
            avvisi.append(
                "Conferma esplicitamente l'ordine cronologico delle colonne del gruppo. "
                "La posizione nel CSV non viene interpretata automaticamente come tempo."
            )
            stato = "da_completare"
        elif (len(specificato) != len(membri)
              or len(set(specificato)) != len(specificato)
              or set(specificato) != set(membri)):
            avvisi.append(
                "L'ordine temporale deve elencare tutte e sole le colonne del gruppo, "
                "ciascuna una volta, separate da punto e virgola."
            )
            stato = "da_completare"
        else:
            colonne_nell_ordine = specificato
        campionamento_temporale = campionamenti.get(id_gruppo, "")
        if campionamento_temporale not in {"regolare", "irregolare"}:
            avvisi.append("Conferma se il campionamento è regolare o irregolare.")
            stato = "da_completare"
        else:
            testo_tempi = (interpretazione.get("tempiTemporaliGruppi") or {}).get(id_gruppo, "")
            unita = (interpretazione.get("unitaTemporaleGruppi") or {}).get(id_gruppo, "")
            richiede_tempi = (
                campionamento_temporale == "irregolare"
                or misura == "Distanza sulle pendenze"
                or (
                    misura == "Dynamic Time Warping"
                    and (interpretazione.get("penalizzazioniDTWGruppi") or {}).get(id_gruppo) == "si"
                )
            )
            if testo_tempi and not isinstance(testo_tempi, str):
                avvisi.append("Indica i timestamp come lista numerica.")
                stato = "da_completare"
            elif not testo_tempi and richiede_tempi:
                avvisi.append(
                    "Per questo confronto servono i timestamp numerici, comuni a tutte "
                    "le righe, nell'ordine confermato delle colonne."
                )
                stato = "da_completare"
            elif testo_tempi:
                try:
                    tempi = _leggi_griglia_temporale(testo_tempi, len(membri))
                    if campionamento_temporale == "regolare" and not _passi_temporali_regolari(tempi):
                        raise ValueError(
                            "I timestamp dichiarati regolari non sono equidistanti. "
                            "Correggi la dichiarazione del campionamento."
                        )
                    if campionamento_temporale == "irregolare" and _passi_temporali_regolari(tempi):
                        raise ValueError(
                            "I timestamp sono equidistanti: correggi la dichiarazione 'irregolare'."
                        )
                    if not unita:
                        raise ValueError("Indica l'unità dei timestamp.")
                    parametri["tempi"] = tempi
                    parametri["unitaTempo"] = unita
                except ValueError as errore:
                    avvisi.append(str(errore))
                    stato = "da_completare"
            elif campionamento_temporale == "regolare":
                # Qui e solo qui gli indici hanno significato di griglia:
                # non sono spacciati per tempi fisici.
                parametri["tempi"] = [float(i) for i in range(len(membri))]
                parametri["unitaTempo"] = "passi"
            parametri["campionamento"] = campionamento_temporale
            if campionamento_temporale == "irregolare" and "tempi" in parametri:
                motivo += " Tutte le righe condividono i timestamp fisici esplicitamente dichiarati."
            if misura == "Dynamic Time Warping":
                costo = (interpretazione.get("costiDTWGruppi") or {}).get(id_gruppo, "assoluto")
                if costo not in {"assoluto", "quadratico"}:
                    avvisi.append("Scegli costo locale assoluto oppure quadratico per DTW.")
                    stato = "da_completare"
                else:
                    parametri["costoLocale"] = costo
                finestra_raw = (interpretazione.get("finestreDTWGruppi") or {}).get(id_gruppo, "")
                if not isinstance(finestra_raw, str) or (
                    finestra_raw.strip()
                    and (not finestra_raw.strip().isdigit()
                         or int(finestra_raw.strip()) >= len(membri))
                ):
                    avvisi.append(
                        "La finestra DTW deve essere vuota (nessun vincolo) oppure "
                        "un intero da 0 al numero di istanti meno uno."
                    )
                    stato = "da_completare"
                elif finestra_raw.strip():
                    parametri["finestra"] = int(finestra_raw.strip())
                politica = (interpretazione.get("penalizzazioniDTWGruppi") or {}).get(id_gruppo, "no")
                if politica not in {"si", "no"}:
                    avvisi.append("Scegli se applicare la penalità sullo sfasamento temporale.")
                    stato = "da_completare"
                elif politica == "si":
                    try:
                        lam = float(str((interpretazione.get("pesiRitardoDTWGruppi") or {}).get(id_gruppo, "")).replace(",", "."))
                        tau = float(str((interpretazione.get("scaleRitardoDTWGruppi") or {}).get(id_gruppo, "")).replace(",", "."))
                    except (ValueError, TypeError):
                        lam, tau = math.nan, math.nan
                    if not math.isfinite(lam) or lam < 0 or (campionamento_temporale == "irregolare" and lam == 0):
                        avvisi.append(
                            "Indica un peso λ finito e non negativo; con tempi irregolari "
                            "richiediamo λ > 0 per non ignorare le distanze temporali."
                        )
                        stato = "da_completare"
                    elif not math.isfinite(tau) or tau <= 0:
                        avvisi.append("Indica una scala temporale τ finita e strettamente positiva.")
                        stato = "da_completare"
                    else:
                        parametri["lambdaRitardo"] = lam
                        parametri["tauRitardo"] = tau
                elif campionamento_temporale == "irregolare":
                    avvisi.append(
                        "La DTW con timestamp irregolari richiede una penalità temporale "
                        "esplicita; la DTW sui soli indici non considera gli intervalli reali."
                    )
                    stato = "da_completare"
            elif misura == "Dissimilarità LCSS normalizzata":
                try:
                    eps = float(str((interpretazione.get("tolleranzeValoreLCSSGruppi") or {}).get(id_gruppo, "")).replace(",", "."))
                    tol_t = float(str((interpretazione.get("tolleranzeTempoLCSSGruppi") or {}).get(id_gruppo, "")).replace(",", "."))
                except (ValueError, TypeError):
                    eps, tol_t = math.nan, math.nan
                if not all(math.isfinite(v) and v >= 0 for v in (eps, tol_t)):
                    avvisi.append("Per LCSS indica tolleranze finite e non negative su valori e tempo.")
                    stato = "da_completare"
                else:
                    parametri["tolleranzaValori"] = eps
                    parametri["tolleranzaTempo"] = tol_t
            elif misura == "Distanza sulle pendenze" and "tempi" not in parametri:
                avvisi.append("Le pendenze richiedono timestamp numerici reali, non indici presunti.")
                stato = "da_completare"

    return {"nome": nome, "colonne": colonne_nell_ordine, "interpretazione": etichetta,
            "misura": misura, "motivo": motivo, "stato": stato, "avvisi": avvisi,
            "idMisura": id_misura, "parametri": parametri,
            "ordineTemporale": colonne_nell_ordine if tipo_gruppo == "tempo" else None,
            "campionamentoTemporale": campionamento_temporale}


RUOLI_GOWER = {"quantita", "livello", "presenza", "binaria", "categoria", "data"}

MISURE_SPECIALIZZATE_CALCOLABILI = {
    "Uguale o diverso",
    "Distanza di Levenshtein normalizzata",
    "Distanza di Hamming normalizzata",
    "Distanza di Damerau–Levenshtein normalizzata",
    "Dissimilarità di Jaccard tra insiemi",
    "Dissimilarità di Dice tra insiemi",
    "Distanza ciclica normalizzata",
    "Distanza di Hamming binaria normalizzata",
    "Dissimilarità di Rogers–Tanimoto",
    "Dissimilarità di Jaccard binaria",
    "Dissimilarità di Dice",
    "Distanza tra coordinate",
    "Dissimilarità coseno",
    "Dissimilarità di Pearson",
    "Dissimilarità di Spearman",
    "Dissimilarità di Kendall τ-b",
    "Dynamic Time Warping",
    "Dissimilarità LCSS normalizzata",
    "Distanza sulle pendenze",
    "Distanza punto per punto",
    "Distanza composizionale di Aitchison",
    "Distanza di Hellinger",
    "Distanza di Jensen–Shannon",
}

ETICHETTE_TRASFORMAZIONE = {
    "zscore": "Z-score",
    "robusto": "Scala robusta (mediana e IQR)",
    "minmax": "Min–max",
    "maxabs": "Max-abs",
    "log": "Logaritmo log(x), per dati strettamente positivi",
    "log1p": "Logaritmo log(1+x), per dati non negativi",
    "costante": "Sostituzione con 0 (feature costante)",
    "nessuno": "Nessuna trasformazione",
}

REGISTRO_MISURE_NUMERICHE = {
    "manhattan": {
        "nome": "Distanza di Manhattan",
        "famiglia": "Minkowski",
        "proprieta": "Metrica; aggrega linearmente gli scarti assoluti.",
    },
    "euclidean": {
        "nome": "Distanza euclidea",
        "famiglia": "Minkowski",
        "proprieta": "Metrica; gli scarti grandi hanno influenza quadratica.",
    },
    "chebyshev": {
        "nome": "Distanza di Chebyshev",
        "famiglia": "Minkowski",
        "proprieta": "Metrica; coincide con il massimo scarto coordinata per coordinata.",
    },
    "minkowski": {
        "nome": "Distanza di Minkowski",
        "famiglia": "Minkowski",
        "proprieta": "È una metrica per q ≥ 1.",
    },
    "weighted_minkowski": {
        "nome": "Distanza di Minkowski pesata",
        "famiglia": "Minkowski",
        "proprieta": "Metrica con pesi strettamente positivi e q ≥ 1.",
    },
    "weighted_chebyshev": {
        "nome": "Distanza di Chebyshev pesata",
        "famiglia": "Geometriche pesate",
        "proprieta": "Metrica con pesi strettamente positivi; massimo degli scarti ponderati.",
    },
    "standardized_euclidean": {
        "nome": "Distanza euclidea standardizzata",
        "famiglia": "Distanze standardizzate",
        "proprieta": "Metrica se tutte le scale utilizzate sono positive.",
    },
    "mahalanobis": {
        "nome": "Distanza di Mahalanobis",
        "famiglia": "Distanze basate sulla covarianza",
        "proprieta": "Metrica se la matrice di covarianza è definita positiva.",
    },
    "mahalanobis_ridge": {
        "nome": "Mahalanobis con covarianza regolarizzata",
        "famiglia": "Distanze basate sulla covarianza",
        "proprieta": "Metrica per S + λI definita positiva (λ > 0).",
    },
    "mahalanobis_pinv": {
        "nome": "Mahalanobis con pseudoinversa",
        "famiglia": "Distanze basate sulla covarianza",
        "proprieta": "Pseudometrica su R^p se la covarianza è singolare; gli scarti nel suo nucleo non contribuiscono.",
    },
    "canberra": {
        "nome": "Distanza di Canberra",
        "famiglia": "Confronti relativi",
        "proprieta": "Metrica; enfatizza gli scarti relativi vicino allo zero.",
    },
    "bray_curtis": {
        "nome": "Dissimilarità di Bray–Curtis",
        "famiglia": "Abbondanze e conteggi",
        "proprieta": "Dissimilarità normalizzata; in generale non soddisfa la triangolarità.",
    },
    "chi_square": {
        "nome": "Distanza χ² simmetrica",
        "famiglia": "Profili di frequenza",
        "proprieta": "Confronta differenze relative alle masse locali delle componenti.",
    },
}


def _lista_numeri_positivi(testo: Any) -> list[float] | None:
    if not isinstance(testo, str) or not testo.strip():
        return None
    if ";" in testo:
        parti = [parte.strip().replace(",", ".") for parte in testo.split(";") if parte.strip()]
    else:
        parti = [parte.strip() for parte in re.split(r"[,\s]+", testo) if parte.strip()]
    try:
        valori = [float(parte) for parte in parti]
    except ValueError:
        return None
    if not valori or any(not math.isfinite(valore) or valore <= 0 for valore in valori):
        return None
    return valori


def _covarianza_empirica_invertibile(
    nomi: list[str], analisi_per_nome: dict[str, dict[str, Any]]
) -> bool:
    """Controlla il rango della covarianza sulle righe complete, senza dipendenze esterne."""
    colonne = [analisi_per_nome[nome].get("valoriNumerici", []) for nome in nomi]
    righe = [
        [float(valore) for valore in valori]
        for valori in zip(*colonne)
        if all(isinstance(valore, (int, float)) for valore in valori)
    ]
    p = len(nomi)
    if len(righe) <= p:
        return False
    medie = [sum(riga[j] for riga in righe) / len(righe) for j in range(p)]
    covarianza = [[
        sum((riga[j] - medie[j]) * (riga[k] - medie[k]) for riga in righe) / (len(righe) - 1)
        for k in range(p)
    ] for j in range(p)]
    scala = max((abs(valore) for riga in covarianza for valore in riga), default=0.0)
    if scala == 0:
        return False
    tolleranza = scala * 1e-10
    rango = 0
    for colonna in range(p):
        pivot = max(range(rango, p), key=lambda riga: abs(covarianza[riga][colonna]))
        if abs(covarianza[pivot][colonna]) <= tolleranza:
            continue
        covarianza[rango], covarianza[pivot] = covarianza[pivot], covarianza[rango]
        pivot_valore = covarianza[rango][colonna]
        for riga in range(rango + 1, p):
            fattore = covarianza[riga][colonna] / pivot_valore
            for k in range(colonna, p):
                covarianza[riga][k] -= fattore * covarianza[rango][k]
        rango += 1
    return rango == p


def _righe_complete_numeriche(
    nomi: list[str], analisi_per_nome: dict[str, dict[str, Any]]
) -> list[list[float]]:
    colonne = [analisi_per_nome[nome].get("valoriNumerici", []) for nome in nomi]
    return [
        [float(valore) for valore in valori]
        for valori in zip(*colonne)
        if all(isinstance(valore, (int, float)) for valore in valori)
    ]


def _inversa_gauss_jordan(matrice: list[list[float]]) -> list[list[float]] | None:
    """Inverte una matrice quadrata con pivoting parziale; None se è numericamente singolare."""
    n = len(matrice)
    if n == 0 or any(len(riga) != n for riga in matrice):
        return None
    scala = max((abs(valore) for riga in matrice for valore in riga), default=0.0)
    if scala == 0:
        return None
    tolleranza = scala * 1e-12
    aumentata = [
        [float(valore) for valore in riga]
        + [1.0 if i == j else 0.0 for j in range(n)]
        for i, riga in enumerate(matrice)
    ]
    for colonna in range(n):
        pivot = max(range(colonna, n), key=lambda i: abs(aumentata[i][colonna]))
        if abs(aumentata[pivot][colonna]) <= tolleranza:
            return None
        aumentata[colonna], aumentata[pivot] = aumentata[pivot], aumentata[colonna]
        divisore = aumentata[colonna][colonna]
        aumentata[colonna] = [valore / divisore for valore in aumentata[colonna]]
        for i in range(n):
            if i == colonna:
                continue
            fattore = aumentata[i][colonna]
            aumentata[i] = [
                valore - fattore * riferimento
                for valore, riferimento in zip(aumentata[i], aumentata[colonna])
            ]
    return [riga[n:] for riga in aumentata]


def _norma_infinito_matrice(matrice: list[list[float]]) -> float:
    return max((sum(abs(valore) for valore in riga) for riga in matrice), default=0.0)


def _diagnosi_numerica(
    nomi: list[str], analisi_per_nome: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Calcola indicatori riproducibili usati dalla proposta automatica."""
    non_costanti = [
        nome for nome in nomi
        if analisi_per_nome[nome].get("statistiche", {}).get("deviazione", 0) > 0
    ]
    scale = []
    for nome in non_costanti:
        stats = analisi_per_nome[nome]["statistiche"]
        scale.append(stats["iqr"] if stats["iqr"] > 0 else stats["deviazione"])
    rapporto_scale = max(scale) / min(scale) if len(scale) >= 2 and min(scale) > 0 else 1.0

    colonne_estreme = [
        nome for nome in nomi
        if analisi_per_nome[nome].get("statistiche", {}).get("quotaEstremi", 0) > 0.01
    ]
    robusto_applicabile = bool(non_costanti) and all(
        analisi_per_nome[nome].get("statistiche", {}).get("iqr", 0) > 0
        for nome in non_costanti
    )
    # La presenza di outlier e l'applicabilità di una scala robusta sono
    # informazioni distinte. Un IQR nullo in una colonna non deve cancellare
    # gli outlier rilevati nelle altre colonne; nella stessa colonna, però,
    # la regola di Tukey con IQR nullo non basta a distinguere un valore raro
    # da un segnale legittimo di una matrice sparsa.
    colonne_outlier = [
        nome for nome in colonne_estreme
        if analisi_per_nome[nome].get("statistiche", {}).get("iqr", 0) > 0
    ]
    colonne_estreme_non_robuste = [
        nome for nome in colonne_estreme if nome not in colonne_outlier
    ]
    colonne_costanti = [
        nome for nome in nomi
        if analisi_per_nome[nome].get("statistiche", {}).get("deviazione") == 0
    ]
    colonne_mancanti = [nome for nome in nomi if analisi_per_nome[nome].get("mancanti", 0) > 0]
    valori_osservati = sum(
        sum(isinstance(valore, (int, float)) for valore in analisi_per_nome[nome].get("valoriNumerici", []))
        for nome in nomi
    )
    zeri_osservati = sum(
        analisi_per_nome[nome].get("statistiche", {}).get("zeri", 0)
        for nome in nomi
    )
    matrice_sparsa = valori_osservati > 0 and zeri_osservati / valori_osservati >= 0.8

    correlazione_massima = 0.0
    coppia_correlata: list[str] = []
    relazioni_coppie: list[dict[str, Any]] = []
    for i, nome_x in enumerate(non_costanti):
        valori_x = analisi_per_nome[nome_x].get("valoriNumerici", [])
        for nome_y in non_costanti[i + 1:]:
            valori_y = analisi_per_nome[nome_y].get("valoriNumerici", [])
            coppie = [
                (float(x), float(y))
                for x, y in zip(valori_x, valori_y)
                if isinstance(x, (int, float)) and isinstance(y, (int, float))
            ]
            if len(coppie) < 4:
                continue
            media_x = sum(x for x, _ in coppie) / len(coppie)
            media_y = sum(y for _, y in coppie) / len(coppie)
            numeratore = sum((x - media_x) * (y - media_y) for x, y in coppie)
            norma_x = math.sqrt(sum((x - media_x) ** 2 for x, _ in coppie))
            norma_y = math.sqrt(sum((y - media_y) ** 2 for _, y in coppie))
            if norma_x == 0 or norma_y == 0:
                continue
            correlazione_firmata = max(-1.0, min(1.0, numeratore / (norma_x * norma_y)))
            correlazione = abs(correlazione_firmata)
            relazioni_coppie.append({
                "colonne": [nome_x, nome_y],
                "correlazione": correlazione_firmata,
                "coppieComplete": len(coppie),
                "intensita": (
                    "perfetta" if 1 - correlazione <= 1e-10 else
                    "forte" if correlazione >= 0.8 else
                    "moderata" if correlazione >= 0.5 else "debole"
                ),
            })
            if correlazione > correlazione_massima:
                correlazione_massima = correlazione
                coppia_correlata = [nome_x, nome_y]

    righe_complete = _righe_complete_numeriche(non_costanti, analisi_per_nome)
    colonne_asimmetriche = [
        {
            "nome": nome,
            "asimmetriaBowley": analisi_per_nome[nome]["statistiche"]["asimmetriaBowley"],
            "numeroOsservati": analisi_per_nome[nome]["statistiche"]["numeroOsservati"],
        }
        for nome in nomi
        if (
            analisi_per_nome[nome].get("statistiche", {}).get("numeroOsservati", 0) >= 8
            and analisi_per_nome[nome].get("statistiche", {}).get("asimmetriaBowley") is not None
            and abs(analisi_per_nome[nome]["statistiche"]["asimmetriaBowley"]) >= 0.3
        )
    ]
    # Diagnosi esplorativa multivariata: separata dal calcolo delle misure.
    # L'assenza di candidati non equivale a certificare assenza di anomalie.
    diagnosi_multivariata: dict[str, Any] = {
        "stato": "non_valutabile",
        "metodo": "Mahalanobis quadrata con covarianza campionaria; limite superiore Q3 + 1,5 IQR",
        "colonne": list(non_costanti),
        "numeroValutate": len(righe_complete),
        "soglia": None,
        "numeroCandidati": 0,
        "candidati": [],
        "motivo": "",
    }
    covarianza_utilizzabile = False
    covarianza_singolare = False
    condizionamento: float | None = None
    righe_minime_covarianza = max(len(non_costanti) + 2, 5 * len(non_costanti))
    campione_limitato = len(righe_complete) < righe_minime_covarianza
    if len(non_costanti) < 2:
        motivo_covarianza = "Servono almeno due colonne quantitative non costanti."
    elif colonne_costanti:
        covarianza_singolare = True
        motivo_covarianza = (
            "Una o più colonne sono costanti: la matrice di covarianza completa è singolare."
        )
    elif len(righe_complete) <= len(non_costanti):
        covarianza_singolare = True
        motivo_covarianza = (
            f"Con {len(righe_complete)} righe complete e {len(non_costanti)} colonne, "
            "la covarianza campionaria non può avere rango pieno."
        )
    else:
        # La soglia 5p è soltanto una cautela sulla stabilità della stima:
        # NON deve impedire di diagnosticare una dipendenza lineare esatta.
        medie = [
            sum(riga[j] for riga in righe_complete) / len(righe_complete)
            for j in range(len(non_costanti))
        ]
        deviazioni = [
            math.sqrt(
                sum((riga[j] - medie[j]) ** 2 for riga in righe_complete)
                / (len(righe_complete) - 1)
            )
            for j in range(len(non_costanti))
        ]
        standardizzate = [
            [(riga[j] - medie[j]) / deviazioni[j] for j in range(len(non_costanti))]
            for riga in righe_complete
        ]
        covarianza_standardizzata = _covarianza(standardizzate)
        inversa = _inversa_gauss_jordan(covarianza_standardizzata)
        if inversa is None:
            covarianza_singolare = True
            motivo_covarianza = (
                "La matrice di covarianza è singolare: alcune colonne contengono "
                "informazioni linearmente dipendenti. Aggiungere righe che rispettano "
                "le stesse relazioni non risolve il problema."
            )
        else:
            condizionamento = (
                _norma_infinito_matrice(covarianza_standardizzata)
                * _norma_infinito_matrice(inversa)
            )
            covarianza_utilizzabile = (
                math.isfinite(condizionamento) and condizionamento <= 1e8
            )
            if not covarianza_utilizzabile:
                motivo_covarianza = (
                    "La covarianza è invertibile ma numericamente mal condizionata: "
                    "Mahalanobis classica potrebbe essere instabile."
                )
            elif campione_limitato:
                motivo_covarianza = (
                    "La covarianza è invertibile e supera il controllo numerico, "
                    f"ma sono disponibili solo {len(righe_complete)} righe complete "
                    f"per {len(non_costanti)} colonne. La soglia prudenziale "
                    f"di {righe_minime_covarianza} non è un requisito matematico: "
                    "la stima può però essere poco stabile."
                )
            else:
                motivo_covarianza = (
                    "La covarianza è invertibile e sufficientemente ben condizionata."
                )

    if len(non_costanti) < 2:
        diagnosi_multivariata["motivo"] = (
            "Servono almeno due colonne quantitative non costanti."
        )
    elif colonne_costanti:
        diagnosi_multivariata["motivo"] = (
            "Sono presenti colonne costanti: la covarianza completa e' singolare. "
            "Non si stimano anomalie multivariate da questo modello."
        )
    elif campione_limitato or len(righe_complete) < 12:
        diagnosi_multivariata["motivo"] = (
            f"Solo {len(righe_complete)} righe complete per {len(non_costanti)} colonne. "
            "Il campione e' troppo piccolo rispetto alla dimensione per questa "
            "segnalazione esplorativa (richieste almeno max(12,5p) righe complete)."
        )
    elif not covarianza_utilizzabile:
        diagnosi_multivariata["motivo"] = (
            "Covarianza singolare o mal condizionata: non si calcolano "
            "punteggi multivariati potenzialmente instabili."
        )
    else:
        # Usa le stesse righe complete della covarianza; la posizione nel CSV
        # e' l'indice tra le righe dati, a partire da 1 (non la riga header).
        riferimento = analisi_per_nome[non_costanti[0]]["valoriNumerici"]
        indici_completi = [
            indice + 1 for indice in range(len(riferimento))
            if all(
                isinstance(analisi_per_nome[nome]["valoriNumerici"][indice], (int, float))
                for nome in non_costanti
            )
        ]
        medie_z = [
            sum(vettore[j] for vettore in standardizzate) / len(standardizzate)
            for j in range(len(non_costanti))
        ]
        punteggi = []
        for indice_riga, vettore in zip(indici_completi, standardizzate):
            centrato = [vettore[j] - medie_z[j] for j in range(len(non_costanti))]
            quadrato = sum(
                centrato[a] * inversa[a][b] * centrato[b]
                for a in range(len(non_costanti)) for b in range(len(non_costanti))
            )
            punteggi.append((indice_riga, max(0.0, quadrato)))
        ordinati_punteggi = sorted(punteggio for _, punteggio in punteggi)
        q1_md = quantile(ordinati_punteggi, 0.25)
        q3_md = quantile(ordinati_punteggi, 0.75)
        if (q1_md is not None and q3_md is not None
                and q3_md > q1_md + 1e-12
                and all(math.isfinite(s) for s in ordinati_punteggi)):
            soglia_md = q3_md + 1.5 * (q3_md - q1_md)
            candidati = sorted(
                (
                    {"riga": i, "punteggio": score}
                    for i, score in punteggi if score > soglia_md
                ),
                key=lambda candidato: candidato["punteggio"], reverse=True,
            )
            diagnosi_multivariata.update({
                "stato": "valutata",
                "soglia": soglia_md,
                "numeroCandidati": len(candidati),
                "candidati": candidati[:20],
                "motivo": (
                    "I punteggi di Mahalanobis sono stimati dalla stessa covarianza "
                    "campionaria: possibili effetti di mascheramento e instabilita'. "
                    "La soglia e' esplorativa, non un test con livello di significativita' "
                    "fissato. Nessuna riga viene rimossa."
                ),
            })
        else:
            diagnosi_multivariata["motivo"] = (
                "Punteggi multivariati non finiti o dispersione interquartilica "
                "dei punteggi nulla: criterio esplorativo non applicabile."
            )

    correlazioni_forti = correlazione_massima >= 0.8
    politica_senza_outlier = "maxabs_automatico" if matrice_sparsa else "zscore_automatico"
    if colonne_outlier:
        id_misura = "manhattan"
        politica = "robusto_forzato" if robusto_applicabile else "zscore_automatico"
        motivo = (
            "Sono presenti valori estremi: la scala robusta limita la loro influenza e "
            "Manhattan non eleva al quadrato gli scarti."
            if robusto_applicabile else
            "Sono presenti valori estremi, ma almeno una colonna ha IQR nullo: viene usato "
            "lo z-score e Manhattan evita di elevare al quadrato gli scarti."
        )
    elif covarianza_singolare:
        id_misura = "euclidean"
        politica = politica_senza_outlier
        motivo = (
            "Attenzione: le colonne selezionate presentano una dipendenza lineare "
            "che rende singolare la covarianza. Mahalanobis classica non è applicabile. "
            "L'Euclidea resta calcolabile, ma può contare più volte la stessa "
            "informazione: verifica se alcune colonne devono essere escluse o "
            "se la ripetizione è intenzionale."
        )
    elif correlazioni_forti and covarianza_utilizzabile and campione_limitato:
        id_misura = "euclidean"
        politica = politica_senza_outlier
        motivo = (
            "Sono state rilevate relazioni lineari forti e la covarianza è invertibile, "
            f"ma le {len(righe_complete)} righe complete sono poche rispetto alle "
            f"{len(non_costanti)} colonne per stimare stabilmente tali relazioni. "
            "Per prudenza viene proposta l'Euclidea; Mahalanobis resta una scelta "
            "avanzata, da usare soltanto se il contesto giustifica la stima della covarianza. "
            + ("Max-abs preserva gli zeri della matrice sparsa." if matrice_sparsa else "Lo z-score assegna alle colonne una scala comune.")
        )
    elif correlazioni_forti and covarianza_utilizzabile:
        id_misura = "mahalanobis"
        politica = politica_senza_outlier
        motivo = (
            "Sono state rilevate relazioni lineari forti e la covarianza è numericamente "
            "utilizzabile; Mahalanobis considera il pattern con cui le colonne variano insieme. "
            + ("Max-abs preserva gli zeri della matrice sparsa." if matrice_sparsa else "Lo z-score assegna alle colonne una scala comune.")
        )
    else:
        id_misura = "euclidean"
        politica = politica_senza_outlier
        motivo = (
            "Non sono presenti outlier rilevanti né una struttura di covarianza forte e "
            "utilizzabile; "
            + ("max-abs preserva gli zeri della matrice sparsa." if matrice_sparsa else "lo z-score assegna alle colonne una scala comune.")
        )

    return {
        "outlier": bool(colonne_outlier),
        "colonneAsimmetriche": colonne_asimmetriche,
        "diagnosiMultivariata": diagnosi_multivariata,
        "robustoApplicabile": robusto_applicabile,
        "colonneOutlier": colonne_outlier,
        "colonneEstremeNonRobuste": colonne_estreme_non_robuste,
        "colonneCostanti": colonne_costanti,
        "colonneMancanti": colonne_mancanti,
        "matriceSparsa": matrice_sparsa,
        "rapportoDispersioni": rapporto_scale,
        "dispersioniSimili": rapporto_scale <= 2,
        "correlazioneMassimaAssoluta": correlazione_massima,
        "coppiaCorrelata": coppia_correlata,
        "relazioniCoppie": relazioni_coppie,
        "correlazioniForti": correlazioni_forti,
        "righeComplete": len(righe_complete),
        "righeMinimeCovarianza": righe_minime_covarianza,
        "covarianzaUtilizzabile": covarianza_utilizzabile,
        "covarianzaSingolare": covarianza_singolare,
        "campioneLimitato": campione_limitato,
        "motivoCovarianza": motivo_covarianza,
        "condizionamentoCovarianza": condizionamento,
        "soglie": {"quotaOutlier": 0.01, "rapportoDispersioni": 2, "correlazione": 0.8, "condizionamento": 1e8},
        "proposta": {
            "idMisura": id_misura,
            "misura": REGISTRO_MISURE_NUMERICHE[id_misura]["nome"],
            "politicaPreelaborazione": politica,
            "motivo": motivo,
        },
    }



def _proponi_gruppi_numerici(
    nomi: list[str], diagnosi: dict[str, Any]
) -> list[dict[str, Any]]:
    """Propone blocchi DISGIUNTI senza inferire il loro significato semantico.

    La radice delle intestazioni e la correlazione tra colonne sono soltanto
    indizi esplorativi. L'utente deve scegliere esplicitamente il tipo di
    gruppo prima che una proposta diventi parte del piano di confronto.
    """
    proposte: list[dict[str, Any]] = []
    occupate: set[str] = set()
    prefissi: dict[str, list[tuple[str, int]]] = {}
    for nome in nomi:
        # Esempi: t1, t2, t3; pressione_01, pressione_02.
        match = re.fullmatch(r"(.+?)[_.\-\s]*([0-9]{1,4})", nome.strip())
        if match is None:
            continue
        radice = match.group(1).rstrip("_.- ").casefold()
        if not radice:
            continue
        prefissi.setdefault(radice, []).append((nome, int(match.group(2))))

    for radice, membri_indicizzati in prefissi.items():
        if len(membri_indicizzati) < 2:
            continue
        if len({indice for _, indice in membri_indicizzati}) != len(membri_indicizzati):
            # Gli indici ripetuti non identificano una successione univoca.
            continue
        membri = [nome for nome in nomi if nome in {n for n, _ in membri_indicizzati}]
        if len(membri) < 2 or any(nome in occupate for nome in membri):
            continue
        proposte.append({
            "nome": f"Gruppo {radice}",
            "colonne": membri,
            "fonte": "intestazioni",
            "motivazione": (
                "Le intestazioni condividono una radice e hanno indici numerici "
                "distinti. Questo non dimostra che siano misure temporali: "
                "verifica il significato e l'ordine delle colonne."
            ),
        })
        occupate.update(membri)

    # Un grafo di correlazioni forti non equivale automaticamente a un blocco:
    # per evitare aggregazioni per transitivita', ogni coppia in un gruppo
    # candidato deve superare direttamente la soglia esplorativa.
    forti: set[frozenset[str]] = set()
    for relazione in diagnosi.get("relazioniCoppie", []):
        coppia = relazione.get("colonne", [])
        correlazione = relazione.get("correlazione")
        if (len(coppia) == 2 and all(nome in nomi for nome in coppia)
                and relazione.get("coppieComplete", 0) >= 4
                and isinstance(correlazione, (int, float))
                and math.isfinite(correlazione)
                and abs(correlazione) >= 0.8):
            forti.add(frozenset(coppia))

    restanti = [nome for nome in nomi if nome not in occupate]
    for primo in restanti:
        if primo in occupate:
            continue
        membri = [primo]
        for altro in restanti:
            if altro == primo or altro in occupate:
                continue
            if all(frozenset((altro, precedente)) in forti for precedente in membri):
                membri.append(altro)
        if len(membri) < 2:
            continue
        proposte.append({
            "nome": f"Gruppo da verificare ({len(proposte) + 1})",
            "colonne": membri,
            "fonte": "correlazione",
            "motivazione": (
                "Ogni coppia del gruppo ha |r di Pearson| >= 0,8 su almeno "
                "quattro osservazioni comuni. La correlazione non identifica "
                "ne' una serie temporale ne' un profilo: conferma se e come "
                "le colonne vadano confrontate insieme."
            ),
        })
        occupate.update(membri)
    return proposte

def analizza_diagnosi_numerica_json(
    testo: str, scelte_json: str = "[]", colonne_json: str = "[]"
) -> str:
    """Diagnosi esplorativa prima del riscalamento, solo su colonne selezionate."""
    try:
        scelte = json.loads(scelte_json or "[]")
        nomi = json.loads(colonne_json or "[]")
        risultato = prepara_tabella(leggi_csv(testo), scelte)
        per_nome = {colonna["nome"]: colonna for colonna in risultato["colonne"]}
        if (
            not isinstance(nomi, list) or not nomi
            or len(nomi) != len(set(nomi))
            or any(
                not isinstance(nome, str) or nome not in per_nome
                or per_nome[nome]["tipo"] not in {"numerica", "numerica_costante"}
                for nome in nomi
            )
        ):
            raise ValueError("Seleziona soltanto colonne numeriche valide.")
        diagnosi = _diagnosi_numerica(nomi, per_nome)
        statistiche_colonne = [
            {
                "nome": nome, "mancanti": per_nome[nome]["mancanti"],
                "statistiche": per_nome[nome].get("statistiche", {}),
            }
            for nome in nomi
        ]
        return json.dumps(
            {"ok": True, "diagnosi": diagnosi, "colonne": statistiche_colonne,
             "gruppiSuggeriti": _proponi_gruppi_numerici(nomi, diagnosi)},
            ensure_ascii=False, separators=(",", ":")
        )
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as errore:
        return json.dumps(
            {"ok": False, "errore": str(errore)},
            ensure_ascii=False, separators=(",", ":")
        )


def crea_diagnosi_decisionale(
    incluse: list[str],
    indipendenti: list[str],
    ruoli: dict[str, str],
    analisi_per_nome: dict[str, dict[str, Any]],
    gruppi_presenti: bool,
) -> dict[str, Any]:
    """Classifica il percorso e formula una proposta prima delle preferenze dell'utente."""
    standard = [nome for nome in indipendenti if ruoli.get(nome) in RUOLI_GOWER]
    solo_quantitative = bool(standard) and len(standard) == len(indipendenti) and all(
        ruoli.get(nome) == "quantita"
        and analisi_per_nome[nome]["tipo"] in {"numerica", "numerica_costante"}
        for nome in standard
    )
    if solo_quantitative and not gruppi_presenti:
        indicatori = _diagnosi_numerica(standard, analisi_per_nome)
        proposta = indicatori["proposta"]
        return {
            "famigliaId": "quantitativo",
            "famiglia": "Dati quantitativi",
            "colonne": standard,
            "indicatori": indicatori,
            "proposta": proposta,
            "richiedeConferma": True,
            "conferma": "Conferma che le colonne rappresentino misure quantitative indipendenti.",
        }
    if standard and len(standard) == len(indipendenti) and not gruppi_presenti:
        quantitative = [
            nome for nome in standard
            if ruoli.get(nome) == "quantita" and analisi_per_nome[nome]["tipo"] in {"numerica", "numerica_costante"}
        ]
        outlier = [
            nome for nome in quantitative
            if analisi_per_nome[nome].get("statistiche", {}).get("quotaEstremi", 0) > 0.01
        ]
        robusta = bool(outlier)
        return {
            "famigliaId": "misto",
            "famiglia": "Dati misti",
            "colonne": standard,
            "indicatori": {
                "outlier": robusta,
                "colonneOutlier": outlier,
                "colonneMancanti": [nome for nome in standard if analisi_per_nome[nome].get("mancanti", 0) > 0],
            },
            "proposta": {
                "idMisura": "gower_robusta" if robusta else "gower_classica",
                "misura": "Dissimilarità di Gower robusta" if robusta else "Dissimilarità di Gower classica",
                "politicaPreelaborazione": "valori_originali",
                "motivo": (
                    "Le variabili hanno tipi differenti e sono presenti outlier quantitativi; "
                    "Gower robusta parte dai valori originali e usa una scala robusta internamente."
                    if robusta else
                    "Le variabili hanno tipi differenti; Gower parte dai valori originali e "
                    "rende confrontabili internamente i contributi."
                ),
            },
            "richiedeConferma": robusta,
            "conferma": "Conferma che i valori estremi segnalati siano osservazioni plausibili." if robusta else "",
        }
    return {
        "famigliaId": "specializzato" if incluse else "vuoto",
        "famiglia": "Percorso specializzato" if incluse else "Nessun dato selezionato",
        "colonne": incluse,
        "indicatori": {},
        "proposta": {
            "idMisura": "da_definire",
            "misura": "Determinata dai gruppi e dal significato delle colonne",
            "politicaPreelaborazione": "specifica_del_percorso",
            "motivo": "Profili, sequenze, composizioni e testi richiedono un ramo dedicato.",
        },
        "richiedeConferma": True,
        "conferma": "Controlla la struttura assegnata alle colonne.",
    }


def _specifica_misura_numerica(
    nomi: list[str],
    analisi_per_nome: dict[str, dict[str, Any]],
    interpretazione: dict[str, Any],
    numero_istanze: int,
) -> dict[str, Any]:
    """Seleziona una misura quantitativa soltanto quando le risposte la giustificano."""
    avvisi: list[str] = []
    stato = "pronto"
    parametri: dict[str, Any] = {}
    alternative: list[dict[str, str]] = []
    confronto = interpretazione.get("confrontoQuantitativo", "")
    scale = interpretazione.get("comparabilitaScale", "")  # compatibilità con risposte salvate
    politica_preelaborazione = "originale"
    diagnosi = _diagnosi_numerica(nomi, analisi_per_nome)
    manuale = interpretazione.get("misuraNumericaManuale", "automatico")

    # Le vecchie risposte restano interpretabili. In assenza di una scelta salvata,
    # il nuovo flusso riscala sempre le quantità ordinarie in modo automatico.
    if confronto in {"relativo", "abbondanza", "frequenze"}:
        politica_preelaborazione = "originale"
    elif scale == "diverse":
        gestione = interpretazione.get("gestioneScale", "")
        if gestione in {"", "ignoto"}:
            politica_preelaborazione = "trasformazioni_candidate"
        elif gestione == "trasforma":
            politica_preelaborazione = "trasformazioni_candidate"
        else:
            politica_preelaborazione = "standardizzazione_interna"
    elif scale == "limitate":
        politica_preelaborazione = "minmax"
    elif scale == "comparabili":
        politica_preelaborazione = "originale"
    else:
        politica_preelaborazione = diagnosi["proposta"]["politicaPreelaborazione"]

    if diagnosi["covarianzaSingolare"]:
        gestione = interpretazione.get("gestioneDipendenzaLineare", "")
        if gestione != "mantieni":
            avvisi.append(
                "Le colonne presentano dipendenza lineare: prima di scegliere la "
                "distanza conferma se vuoi mantenere tutte le caratteristiche, "
                "accettando che informazioni ripetute influenzino il risultato, "
                "oppure escludi le colonne ridondanti."
            )
            stato = "da_completare"
        else:
            # La conferma non rende invertibile la covarianza: abilita
            # soltanto misure di coordinate che restano ben definite.
            pass

    minimi = [analisi_per_nome[nome].get("statistiche", {}).get("minimo") for nome in nomi]
    non_negative = all(valore is not None and valore >= 0 for valore in minimi)
    if confronto == "":
        id_misura = "euclidean"
        avvisi.append("Indica quale tipo di differenza debba definire la dissimilarità.")
        stato = "da_completare"
    elif confronto == "relativo":
        id_misura = "canberra"
        politica_preelaborazione = "originale"
        if not non_negative:
            avvisi.append("Il percorso relativo richiede quantità non negative in questa guida decisionale.")
            stato = "da_completare"
        if interpretazione.get("valoriVicinoZero") == "":
            avvisi.append("Indica se valori nulli o prossimi a zero siano frequenti.")
            stato = "da_completare"
        elif interpretazione.get("valoriVicinoZero") in {"si", "ignoto"}:
            avvisi.append("Canberra può far dominare le componenti piccole: verifica che questo effetto sia desiderato.")
        alternative.append({
            "id": "bray_curtis", "nome": REGISTRO_MISURE_NUMERICHE["bray_curtis"]["nome"],
            "motivo": "Da valutare se i dati rappresentano abbondanze e interessa la differenza complessiva.",
        })
    elif confronto == "abbondanza":
        id_misura = "bray_curtis"
        politica_preelaborazione = "originale"
        if not non_negative:
            avvisi.append("Bray–Curtis richiede valori non negativi.")
            stato = "da_completare"
        alternative.append({
            "id": "canberra", "nome": REGISTRO_MISURE_NUMERICHE["canberra"]["nome"],
            "motivo": "Alternativa se devono contare soprattutto le differenze relative componente per componente.",
        })
    elif confronto == "frequenze":
        id_misura = "chi_square"
        politica_preelaborazione = "originale"
        if not non_negative:
            avvisi.append("La distanza χ² richiede frequenze o quantità non negative.")
            stato = "da_completare"
        alternative.append({
            "id": "bray_curtis", "nome": REGISTRO_MISURE_NUMERICHE["bray_curtis"]["nome"],
            "motivo": "Alternativa se non si vuole dare particolare rilievo alle componenti rare.",
        })
    else:
        aggregazione = interpretazione.get("aggregazioneScarti", "automatico")
        mappa = {
            "lineare": "manhattan",
            "quadratica": "euclidean",
            "massimo": "chebyshev",
            "minkowski": "minkowski",
        }
        scelta_automatica = aggregazione in {"", "automatico", "ignoto"} or confronto == "ignoto"
        id_misura = diagnosi["proposta"]["idMisura"] if scelta_automatica else mappa.get(aggregazione, "euclidean")
        if aggregazione == "minkowski":
            try:
                q = float(interpretazione.get("ordineMinkowski", ""))
            except (TypeError, ValueError):
                q = math.nan
            if not math.isfinite(q) or q < 1:
                avvisi.append("Inserisci un esponente q numerico maggiore o uguale a 1.")
                stato = "da_completare"
            else:
                parametri["q"] = q

        dipendenza = interpretazione.get("dipendenzaCoordinate", "") if len(nomi) >= 2 else "no"
        if dipendenza == "si":
            id_misura = "mahalanobis"
            politica_preelaborazione = "originale"
            # La validita' della misura effettivamente scelta viene controllata
            # DOPO l'eventuale scelta manuale: niente avvisi obsoleti se l'utente
            # passa a regolarizzazione o pseudoinversa.

        if scelta_automatica and id_misura == "mahalanobis" and (
            dipendenza == "no" or not diagnosi["covarianzaUtilizzabile"]
        ):
            id_misura = "euclidean"
            politica_preelaborazione = "zscore_automatico"

        importanza = interpretazione.get("importanzaCoordinate", "uguale") if len(nomi) >= 2 else "uguale"
        if importanza == "diversa" and id_misura != "mahalanobis":
            pesi = _lista_numeri_positivi(interpretazione.get("pesiQuantitativi"))
            if pesi is None or len(pesi) != len(nomi):
                avvisi.append(f"Inserisci esattamente {len(nomi)} pesi strettamente positivi.")
                stato = "da_completare"
            elif id_misura == "chebyshev":
                avvisi.append("La parametrizzazione pesata adottata è definita per Minkowski con q finito; scegli un’altra aggregazione o pesi uguali.")
                stato = "da_completare"
            else:
                parametri["pesi"] = pesi
                if id_misura == "manhattan":
                    parametri["q"] = 1
                elif id_misura == "euclidean":
                    parametri["q"] = 2
                id_misura = "weighted_minkowski"

        if politica_preelaborazione == "standardizzazione_interna":
            if id_misura == "euclidean":
                id_misura = "standardized_euclidean"
            elif id_misura not in {"mahalanobis"}:
                avvisi.append("La standardizzazione interna disponibile è euclidea; per questa misura scegli la trasformazione preventiva delle colonne.")
                stato = "da_completare"

        for alternativa in ("manhattan", "euclidean", "chebyshev"):
            if alternativa != id_misura:
                alternative.append({
                    "id": alternativa,
                    "nome": REGISTRO_MISURE_NUMERICHE[alternativa]["nome"],
                    "motivo": "Alternativa con una diversa sensibilità alla distribuzione degli scarti.",
                })

    # La scelta esplicita nel piano prevale sulla raccomandazione, ma non sui
    # vincoli matematici della misura. Nessun fallback silenzioso.
    opzioni_manuali = {
        "euclidean", "manhattan", "chebyshev", "minkowski",
        "weighted_minkowski", "weighted_chebyshev", "mahalanobis",
        "mahalanobis_ridge", "mahalanobis_pinv",
        "canberra", "bray_curtis", "chi_square",
    }
    if manuale not in ("", "automatico"):
        if manuale not in opzioni_manuali:
            raise ValueError("La misura numerica selezionata non è riconosciuta.")
        id_misura = manuale
        parametri = {}
        if manuale in {"minkowski", "weighted_minkowski"}:
            try:
                q = float(interpretazione.get("ordineMisuraManuale", "2"))
            except (ValueError, TypeError):
                q = math.nan
            if not math.isfinite(q) or q < 1:
                avvisi.append("L'esponente q deve essere un numero finito maggiore o uguale a 1.")
                stato = "da_completare"
            else:
                parametri["q"] = q
        if manuale in {"weighted_minkowski", "weighted_chebyshev"}:
            pesi = _lista_numeri_positivi(interpretazione.get("pesiMisuraManuale", ""))
            if pesi is None or len(pesi) != len(nomi):
                avvisi.append(f"Per la misura pesata servono {len(nomi)} pesi strettamente positivi, nell'ordine delle colonne selezionate.")
                stato = "da_completare"
            else:
                # Normalizzazione solo facoltativa: conserviamo i pesi scelti.
                parametri["pesi"] = pesi
        if manuale in {"mahalanobis", "mahalanobis_ridge", "mahalanobis_pinv"}:
            politica_preelaborazione = "originale"
            if manuale == "mahalanobis_ridge":
                try:
                    valore = float(str(interpretazione.get("lambdaMahalanobis", "")).replace(",", "."))
                except (ValueError, TypeError):
                    valore = math.nan
                if not math.isfinite(valore) or valore <= 0:
                    avvisi.append(
                        "Per la regolarizzazione indica esplicitamente λ > 0, "
                        "nelle unità al quadrato delle coordinate originali."
                    )
                    stato = "da_completare"
                else:
                    parametri["lambda"] = valore
            elif manuale == "mahalanobis_pinv":
                try:
                    valore = float(str(interpretazione.get("tolleranzaPseudoinversa", "")).replace(",", "."))
                except (ValueError, TypeError):
                    valore = math.nan
                if not math.isfinite(valore) or not 1e-12 <= valore <= 0.1:
                    avvisi.append(
                        "Per la pseudoinversa indica la tolleranza relativa sullo spettro "
                        "fra 1e-12 e 0.1, confermandola esplicitamente."
                    )
                    stato = "da_completare"
                else:
                    parametri["tolleranzaRelativa"] = valore
        elif manuale in {"canberra", "bray_curtis", "chi_square"}:
            # Le trasformazioni centrate possono rendere negative le abbondanze.
            politica_preelaborazione = "originale"
            if manuale in {"bray_curtis", "chi_square"} and not non_negative:
                avvisi.append("Questa misura richiede valori non negativi.")
                stato = "da_completare"
        elif politica_preelaborazione in {"originale", "standardizzazione_interna"}:
            politica_preelaborazione = diagnosi["proposta"]["politicaPreelaborazione"]
        alternative = [
            {"id": candidato, "nome": specifica["nome"],
             "motivo": "Disponibile come scelta esplicita, subordinata ai requisiti matematici."}
            for candidato, specifica in REGISTRO_MISURE_NUMERICHE.items()
            if candidato != id_misura
        ]

    # Verifica l'effettiva misura, senza trasferire blocchi della proposta
    # automatica a una variante esplicitamente selezionata.
    if id_misura == "mahalanobis":
        if not diagnosi["covarianzaUtilizzabile"] or not _covarianza_empirica_invertibile(
            nomi, analisi_per_nome
        ):
            avvisi.append(
                "Mahalanobis classica richiede una covarianza non singolare e ben "
                "condizionata. Puoi rivedere le colonne oppure selezionare "
                "esplicitamente una regolarizzazione o una pseudoinversa."
            )
            stato = "da_completare"
    elif id_misura in {"mahalanobis_ridge", "mahalanobis_pinv"} and parametri:
        try:
            _prepara_covarianza_mahalanobis(
                _righe_complete_numeriche(nomi, analisi_per_nome), id_misura, parametri
            )
        except ValueError as errore:
            avvisi.append(str(errore))
            stato = "da_completare"

    # Una trasformazione richiesta manualmente non puo' essere ignorata
    # dalla politica diagnostica predefinita. Le misure che dipendono dal
    # significato dei valori originali sono escluse da questa regola.
    geometriche = {
        "euclidean", "manhattan", "chebyshev", "minkowski",
        "weighted_minkowski", "weighted_chebyshev",
    }
    if (
        id_misura in geometriche
        and politica_preelaborazione == "originale"
        and any(
            analisi_per_nome[nome].get("sceltaMetodo", "auto") not in {"auto", "", None}
            for nome in nomi
        )
    ):
        politica_preelaborazione = "trasformazioni_candidate"

    # Le scelte confermate del riscalamento governano le distanze
    # coordinate per coordinata. Le misure relative e Mahalanobis restano
    # sui valori originali per non alterarne il significato.
    nota_preelaborazione = ""
    if interpretazione.get("riscalamentoConfermato"):
        if id_misura == "standardized_euclidean":
            id_misura = "euclidean"
            parametri.pop("scale", None)
        geometriche = {
            "euclidean", "manhattan", "chebyshev", "minkowski",
            "weighted_minkowski", "weighted_chebyshev",
        }
        if id_misura in geometriche:
            politica_preelaborazione = "trasformazioni_candidate"
        elif id_misura in {"mahalanobis", "mahalanobis_ridge", "mahalanobis_pinv",
                          "canberra", "bray_curtis", "chi_square"}:
            politica_preelaborazione = "originale"
            nota_preelaborazione = (
                "Questa misura usa i valori originali, non quelli riscalati: "
                "la matrice trasformata rimane disponibile per consultazione."
            )

    misura = REGISTRO_MISURE_NUMERICHE[id_misura]
    return {
        "idMisura": id_misura,
        "metodo": misura["nome"],
        "famiglia": misura["famiglia"],
        "proprieta": misura["proprieta"],
        "parametri": parametri,
        "alternative": alternative,
        "avvisi": avvisi,
        "stato": stato,
        "politicaPreelaborazione": politica_preelaborazione,
        "diagnosiAutomatica": diagnosi,
        "notaPreelaborazione": nota_preelaborazione,
    }


def _politica_mancanti(
    nomi: list[str],
    analisi_per_nome: dict[str, dict[str, Any]],
    percorso: dict[str, Any],
    interpretazione: dict[str, Any],
    numero_istanze: int,
) -> dict[str, Any]:
    """Dichiara, senza impliciti, come il percorso tratta i valori mancanti."""
    tipo_percorso = percorso["tipo"]
    colonne = [nome for nome in nomi if analisi_per_nome[nome]["mancanti"] > 0]
    if not colonne:
        return {
            "presenza": False,
            "strategia": "non_necessaria",
            "descrizione": "Nessun valore mancante nelle colonne utilizzate.",
            "pronta": True,
            "colonne": [],
        }
    if tipo_percorso == "gower":
        return {
            "presenza": True,
            "strategia": "esclusione_pairwise",
            "descrizione": (
                "Gower omette, per ogni coppia di righe, i contributi non osservabili "
                "e ricalcola il denominatore sui soli contributi disponibili."
            ),
            "pronta": True,
            "colonne": colonne,
        }
    if tipo_percorso == "numerico":
        configurate = interpretazione.get("mancantiNumericiPerColonna") or {}
        if not isinstance(configurate, dict):
            raise ValueError("Le strategie per i mancanti numerici non sono valide.")
        ammesse = {"escludi_riga", "imputa_mediana", "imputa_media", "zero", "pairwise"}
        strategie = {
            nome: configurate.get(nome, "")
            for nome in colonne
        }
        non_definite = [
            nome for nome, strategia in strategie.items()
            if strategia not in ammesse
        ]
        if non_definite:
            return {
                "presenza": True,
                "strategia": "da_definire",
                "descrizione": (
                    "Scegli come trattare le caselle vuote nelle colonne: "
                    + ", ".join(non_definite) + "."
                ),
                "pronta": False,
                "colonne": colonne,
                "perColonna": strategie,
            }

        # Il confronto per coordinate comuni e' definito soltanto per
        # le distanze Minkowski (incluse euclidea/Manhattan) e Chebyshev.
        # Non e' una surrogazione per Mahalanobis o le distanze relative.
        if "pairwise" in strategie.values() and percorso.get("idMisura") not in {"euclidean", "manhattan", "chebyshev", "minkowski",
               "weighted_minkowski", "weighted_chebyshev"}:
            return {
                "presenza": True, "strategia": "non_compatibile",
                "descrizione": (
                    "Il confronto sulle sole coordinate osservate da entrambe le righe "
                    "e' disponibile per Manhattan, euclidea, Minkowski (anche pesata) "
                    "e Chebyshev. Seleziona una di queste misure oppure scegli "
                    "esclusione/imputazione per i mancanti."
                ),
                "pronta": False, "colonne": colonne, "perColonna": strategie,
            }
        etichette = {
            "escludi_riga": "esclude le righe in cui il valore manca",
            "imputa_mediana": "sostituisce il vuoto con la mediana osservata",
            "imputa_media": "sostituisce il vuoto con la media osservata",
            "zero": "sostituisce esplicitamente il vuoto con zero",
            "pairwise": "ignora il vuoto soltanto nelle coppie coinvolte",
        }
        colonne_esclusione = [
            nome for nome, strategia in strategie.items()
            if strategia == "escludi_riga"
        ]
        righe_totali = max(
            (len(analisi_per_nome[nome].get("valoriNumerici", [])) for nome in nomi),
            default=0,
        )
        righe_utilizzabili = sum(
            all(
                isinstance(analisi_per_nome[nome]["valoriNumerici"][indice], (int, float))
                for nome in colonne_esclusione
            )
            for indice in range(righe_totali)
        )
        if righe_utilizzabili < 2:
            return {
                "presenza": True,
                "strategia": "configurazione_per_colonna",
                "descrizione": (
                    "Le esclusioni richieste lasciano meno di due righe confrontabili. "
                    "Modifica la strategia oppure completa i dati."
                ),
                "pronta": False,
                "colonne": colonne,
                "perColonna": strategie,
                "righeUtilizzabili": righe_utilizzabili,
            }
        return {
            "presenza": True,
            "strategia": "configurazione_per_colonna",
            "descrizione": (
                "Per i mancanti numerici: "
                + "; ".join(f"{nome}: {etichette[strategia]}" for nome, strategia in strategie.items())
                + ". I parametri di centro e scala sono stimati sui valori osservati."
                + (
                    " Nei confronti a coppie si usano soltanto le coordinate comuni, "
                    "con media pesata degli scarti elevati a q; se non ne esistono, "
                    "il contributo di questo percorso e' non disponibile."
                    if "pairwise" in strategie.values() else ""
                )
            ),
            "pronta": True,
            "colonne": colonne,
            "perColonna": strategie,
            "righeUtilizzabili": righe_utilizzabili,
        }
    if tipo_percorso == "gruppo":
        id_gruppo = percorso.get("idGruppo", "")
        tipo_gruppo = percorso.get("tipoGruppo", "altro")
        strategia = interpretazione.get(f"mancanti-gruppo-{id_gruppo}", "")
        if tipo_gruppo == "tempo_coppie":
            if strategia not in {"salta_slot", "escludi_percorso"}:
                return {
                    "presenza": True, "strategia": "da_definire", "pronta": False,
                    "colonne": colonne,
                    "descrizione": (
                        "Sono presenti coppie con celle vuote: scegli se ignorare "
                        "soltanto le coppie completamente vuote o escludere l'intera "
                        "serie della riga. Timestamp e valori non sono imputati."
                    ),
                }
            return {
                "presenza": True, "strategia": strategia, "pronta": True,
                "colonne": colonne,
                "descrizione": (
                    "Sono ignorate soltanto coppie tempo-valore entrambe vuote. "
                    "Una coppia parziale è un errore e non viene ricostruita."
                    if strategia == "salta_slot" else
                    "Una riga con una qualsiasi coppia vuota o parziale "
                    "non contribuisce a questo percorso temporale."
                ),
            }
        if tipo_gruppo == "vettore_binario":
            if strategia not in {"escludi_percorso", "zero", "pairwise"}:
                return {
                    "presenza": True, "strategia": "da_definire",
                    "descrizione": "Per le presenze mancanti scegli esplicitamente "
                    "se ignorare il gruppo nelle coppie coinvolte, confrontare "
                    "soltanto le coordinate osservate da entrambe le righe, "
                    "oppure confermare che ogni vuoto significhi assenza (zero).",
                    "pronta": False, "colonne": colonne,
                }
            return {
                "presenza": True, "strategia": strategia,
                "descrizione": (
                    "Una riga incompleta non contribuisce a questo vettore binario."
                    if strategia == "escludi_percorso" else
                    "Per ogni coppia di righe si confrontano solo le caratteristiche "
                    "osservate in entrambe. Se non ne esistono, il contributo è "
                    "non disponibile, non zero. I doppi zeri osservati sono validi; "
                    "per Dice le sole doppie assenze non definiscono la misura."
                    if strategia == "pairwise" else
                    "Ogni vuoto del vettore binario è interpretato esplicitamente "
                    "come assenza (zero)."
                ),
                "pronta": True, "colonne": colonne,
                "statiPerColonna": (
                    interpretazione.get("statiMancantiPerColonna") or {}
                    if interpretazione.get("significatoMancanti") == "misto" else {}
                ),
            }
        ammesse = {"escludi_percorso", "zero"}
        if tipo_gruppo == "tempo":
            ammesse.add("interpola_lineare")
        # Per probabilità e istogrammi non si imputano media o mediana:
        # altererebbero la massa senza una giustificazione semantica.
        elif tipo_gruppo in {"ripetute", "parti", "coordinate"}:
            ammesse.update({"imputa_mediana", "imputa_media"})
            if percorso.get("idMisura") in {"euclidean", "manhattan", "chebyshev", "minkowski",
               "weighted_minkowski", "weighted_chebyshev"}:
                ammesse.add("pairwise")
        if strategia not in ammesse:
            return {
                "presenza": True,
                "strategia": "da_definire",
                "descrizione": (
                    f"Scegli come trattare le caselle vuote nel gruppo “{percorso['titolo']}”."
                    + (
                        " Il confronto pairwise non e' compatibile con la misura "
                        "o il significato di questo gruppo: scegli Minkowski/Manhattan/"
                        "euclidea/Chebyshev su coordinate, oppure un'altra strategia."
                        if strategia == "pairwise" else ""
                    )
                ),
                "pronta": False,
                "colonne": colonne,
            }

        valori = [analisi_per_nome[nome].get("valoriNumerici", []) for nome in nomi]
        if strategia == "escludi_percorso":
            righe_utilizzabili = sum(
                all(isinstance(colonna[indice], (int, float)) for colonna in valori)
                for indice in range(numero_istanze)
            )
            descrizione = (
                "Le righe con almeno una casella vuota non contribuiscono a questo "
                "percorso, ma possono ancora essere confrontate dagli altri percorsi."
            )
        elif strategia == "interpola_lineare":
            righe_utilizzabili = sum(
                bool(valori)
                and all(len(colonna) == numero_istanze for colonna in valori)
                and isinstance(valori[0][indice], (int, float))
                and isinstance(valori[-1][indice], (int, float))
                for indice in range(numero_istanze)
            )
            descrizione = (
                "I vuoti interni alla serie sono interpolati linearmente. Una riga con "
                "un vuoto iniziale o finale non contribuisce a questo percorso."
            )
        elif strategia == "pairwise":
            righe_utilizzabili = sum(
                any(isinstance(colonna[indice], (int, float)) for colonna in valori)
                for indice in range(numero_istanze)
            )
            descrizione = (
                "Per ogni coppia usa soltanto le coordinate osservate in entrambe "
                "le righe; distanza non disponibile se nessuna coordinata e' comune. "
                "Minkowski usa la media pesata degli scarti sulle coordinate comuni."
            )
        elif strategia == "imputa_mediana":
            righe_utilizzabili = numero_istanze
            descrizione = "Ogni vuoto è sostituito con la mediana osservata della stessa colonna."
        elif strategia == "imputa_media":
            righe_utilizzabili = numero_istanze
            descrizione = "Ogni vuoto è sostituito con la media osservata della stessa colonna."
        else:
            righe_utilizzabili = numero_istanze
            descrizione = "Ogni vuoto è sostituito esplicitamente con zero."
        if righe_utilizzabili < 2:
            return {
                "presenza": True,
                "strategia": strategia,
                "descrizione": descrizione + " Restano meno di due righe utilizzabili.",
                "pronta": False,
                "colonne": colonne,
                "righeUtilizzabili": righe_utilizzabili,
            }
        return {
            "presenza": True,
            "strategia": strategia,
            "descrizione": descrizione,
            "pronta": True,
            "colonne": colonne,
            "righeUtilizzabili": righe_utilizzabili,
        }
    if tipo_percorso == "separato":
        nome = nomi[0]
        configurate = interpretazione.get("mancantiSpecializzatiPerColonna") or {}
        if not isinstance(configurate, dict):
            raise ValueError("Le strategie per i mancanti testuali non sono valide.")
        strategia = configurate.get(nome, "")
        metodo = percorso.get("metodo")
        if metodo in {
            "Dissimilarità di Jaccard tra insiemi",
            "Dissimilarità di Dice tra insiemi",
        }:
            ammesse = {"escludi_percorso", "insieme_vuoto"}
        elif metodo == "Distanza ciclica normalizzata":
            ammesse = {"escludi_percorso"}
        else:
            ammesse = {"escludi_percorso", "stringa_vuota"}
        if strategia not in ammesse:
            return {
                "presenza": True,
                "strategia": "da_definire",
                "descrizione": f"Scegli come trattare le caselle vuote nella colonna “{nome}” senza attribuire loro una distanza nulla.",
                "pronta": False,
                "colonne": colonne,
            }
        osservate = numero_istanze - analisi_per_nome[nome]["mancanti"]
        pronta = strategia in {"stringa_vuota", "insieme_vuoto"} or osservate >= 2
        descrizione = (
            "Le coppie che coinvolgono una casella vuota non ricevono un contributo da questo percorso."
            if strategia == "escludi_percorso"
            else "La casella vuota è trattata esplicitamente come insieme vuoto osservato."
            if strategia == "insieme_vuoto"
            else "La casella vuota è trattata esplicitamente come testo di lunghezza zero."
        )
        if not pronta:
            descrizione += " Restano meno di due valori osservati."
        return {
            "presenza": True,
            "strategia": strategia,
            "descrizione": descrizione,
            "pronta": pronta,
            "colonne": colonne,
            "righeUtilizzabili": numero_istanze if strategia in {"stringa_vuota", "insieme_vuoto"} else osservate,
        }
    return {
        "presenza": True,
        "strategia": "da_definire",
        "descrizione": (
            "Il significato dei mancanti è stato raccolto, ma questo percorso richiede "
            "ancora una scelta operativa tra imputazione, esclusione o un metodo pairwise."
        ),
        "pronta": False,
        "colonne": colonne,
    }


def _preelaborazione_numerica(
    nomi: list[str],
    analisi_per_nome: dict[str, dict[str, Any]],
    metodo_forzato: str | None = None,
) -> dict[str, Any]:
    passi = []
    for nome in nomi:
        colonna = analisi_per_nome[nome]
        scelta_esplicita = colonna.get("sceltaMetodo", "auto") not in {"auto", "", None}
        metodo = (
            "costante"
            if colonna.get("tipo") == "numerica_costante"
            else colonna.get("metodo", "nessuno") if scelta_esplicita
            else metodo_forzato or colonna.get("metodo", "nessuno")
        )
        passi.append({
            "colonna": nome,
            "metodo": metodo,
            "etichetta": ETICHETTE_TRASFORMAZIONE.get(metodo, metodo),
        })
    trasformazioni = [passo for passo in passi if passo["metodo"] != "nessuno"]
    return {
        "origine": "tabella_trasformata",
        "etichettaOrigine": "Tabella trasformata per questo percorso",
        "usaTabellaTrasformata": True,
        "passi": passi,
        "descrizione": (
            "Le trasformazioni elencate vengono applicate soltanto alle colonne di "
            "questo percorso."
            if trasformazioni
            else "Le scale sono mantenute: nessuna trasformazione è applicata."
        ),
    }


def _preelaborazione_originale(descrizione: str) -> dict[str, Any]:
    return {
        "origine": "valori_originali",
        "etichettaOrigine": "Valori originali",
        "usaTabellaTrasformata": False,
        "passi": [],
        "descrizione": descrizione,
    }


def _controlla_compatibilita_preelaborazione(
    percorso: dict[str, Any],
    analisi_per_nome: dict[str, dict[str, Any]],
    interpretazione: dict[str, Any],
    preelaborazione: dict[str, Any],
) -> dict[str, Any]:
    """Confronta la scelta preliminare con la rappresentazione effettivamente usata.

    Le misure che richiedono valori originali non vengono cambiate
    silenziosamente. La conferma generale del riscalamento non equivale
    a confermare di IGNORARLO in un particolare blocco.
    """
    usa_trasformata = bool(preelaborazione["usaTabellaTrasformata"])
    origine = "trasformata" if usa_trasformata else "originale"
    metodi = {
        nome: analisi_per_nome[nome].get("metodo", "nessuno")
        for nome in percorso["colonne"]
        if analisi_per_nome[nome]["tipo"] in {"numerica", "numerica_costante"}
    }
    # Le colonne costanti sono già prive di variabilità.
    efficaci = {
        nome: metodo for nome, metodo in metodi.items() if metodo != "costante"
    }
    ha_riscalamenti = bool(interpretazione.get("riscalamentoConfermato")) and any(
        metodo != "nessuno" for metodo in efficaci.values()
    )
    tipo = percorso["tipo"]
    id_gruppo = str(percorso.get("idGruppo") or "")
    richiesta: str | None = None
    descrizione = (
        "Questo percorso applica le trasformazioni indicate nel piano."
        if usa_trasformata
        else "Questo percorso utilizza i valori originali delle colonne."
    )

    if ha_riscalamenti and tipo == "gruppo" and not usa_trasformata:
        richiesta = "originali_gruppo"
        descrizione = (
            "Le trasformazioni numeriche confermate NON vengono applicate a "
            f"“{percorso['titolo']}”: la misura {percorso['metodo']} "
            "usa le coordinate originali. Riscalare separatamente le colonne "
            "potrebbe alterare profilo, andamento, composizione o confronto temporale."
        )
        confermato = (
            (interpretazione.get("confermeValoriOriginaliGruppi") or {}).get(id_gruppo)
            == "si"
        )
    elif ha_riscalamenti and tipo == "gruppo" and usa_trasformata and len(set(efficaci.values())) > 1:
        richiesta = "misti_gruppo"
        descrizione = (
            f"Nel gruppo “{percorso['titolo']}” le colonne vengono trasformate "
            "con metodi differenti. La distanza resta calcolabile, ma "
            "la loro importanza relativa dipende dalla scelta delle trasformazioni. "
            "Conferma che tale combinazione sia intenzionale."
        )
        confermato = (
            (interpretazione.get("confermeRiscalamentiMistiGruppi") or {}).get(id_gruppo)
            == "si"
        )
    elif ha_riscalamenti and tipo == "numerico" and not usa_trasformata:
        richiesta = "originali_numerico"
        descrizione = (
            f"La misura {percorso['metodo']} usa i valori originali, non le "
            "trasformazioni preliminari confermate. Applicare quelle "
            "trasformazioni cambierebbe il significato del confronto. "
            "Conferma esplicitamente di mantenere la misura sui valori originali."
        )
        confermato = interpretazione.get("confermaValoriOriginaliNumerici") == "si"
    else:
        confermato = True

    if richiesta and not confermato:
        percorso["stato"] = "da_completare"
        percorso.setdefault("avvisi", []).append(descrizione)
    return {
        "origineEffettiva": origine,
        "richiesta": richiesta,
        "confermata": bool(confermato),
        "metodiPreliminari": metodi,
        "descrizione": descrizione,
    }


def _completa_specifica_percorso(
    percorso: dict[str, Any],
    analisi_per_nome: dict[str, dict[str, Any]],
    interpretazione: dict[str, Any],
    numero_istanze: int,
) -> dict[str, Any]:
    """Aggiunge origine, trasformazioni, mancanti e disponibilità del calcolo."""
    tipo = percorso["tipo"]
    nomi = percorso["colonne"]
    if tipo == "numerico":
        politica = percorso.get("politicaPreelaborazione", "trasformazioni_candidate")
        if politica == "originale":
            preelaborazione = _preelaborazione_originale(
                "La misura confronta direttamente i valori originali, senza applicare "
                "il riscalamento preliminare: eventuali rapporti o normalizzazioni "
                "sono definiti dalla misura stessa."
            )
        elif politica == "standardizzazione_interna":
            preelaborazione = _preelaborazione_originale(
                "Le scale restano nei dati originali e vengono incorporate nella distanza selezionata."
            )
        elif politica == "minmax":
            preelaborazione = _preelaborazione_numerica(nomi, analisi_per_nome, "minmax")
            preelaborazione["descrizione"] = (
                "Ogni colonna è riportata nell’intervallo [0,1]. Quando disponibili, "
                "sono preferibili limiti teorici agli estremi campionari."
            )
        elif politica == "trasformazioni_candidate":
            preelaborazione = _preelaborazione_numerica(nomi, analisi_per_nome)
        elif politica == "zscore_prudenziale":
            preelaborazione = _preelaborazione_numerica(nomi, analisi_per_nome, "zscore")
            preelaborazione["descrizione"] = (
                "Le colonne misurano quantità diverse o il loro significato non è noto con certezza. "
                "Sono quindi riequilibrate con lo z-score, così nessuna prevale soltanto perché usa numeri più grandi."
            )
        elif politica == "zscore_automatico":
            preelaborazione = _preelaborazione_numerica(nomi, analisi_per_nome, "zscore")
            preelaborazione["descrizione"] = (
                "Lo z-score e' la proposta predefinita per le colonne non "
                "configurate manualmente. Le scelte esplicite per colonna prevalgono; "
                "le colonne costanti ricevono contributo nullo."
            )
        elif politica == "maxabs_automatico":
            preelaborazione = _preelaborazione_numerica(nomi, analisi_per_nome, "maxabs")
            preelaborazione["descrizione"] = (
                "Max-abs e' la proposta predefinita per i dati sparsi; "
                "le scelte esplicite di trasformazione per colonna prevalgono "
                "e le colonne costanti ricevono contributo nullo."
            )
        elif politica == "robusto_forzato":
            preelaborazione = _preelaborazione_numerica(nomi, analisi_per_nome, "robusto")
            preelaborazione["descrizione"] = (
                "La centratura sulla mediana e divisione per IQR e' la proposta "
                "predefinita in presenza di valori estremi. Le scelte manuali "
                "prevalgono. Questa scala non elimina ne' tronca gli outlier."
            )
        else:
            preelaborazione = _preelaborazione_originale(
                "Il sito non ha rilevato differenze di scala che richiedano un riequilibrio."
            )
    elif tipo == "gower":
        preelaborazione = _preelaborazione_originale(
            "Gower parte dai valori originali e costruisce internamente contributi "
            "confrontabili; l’anteprima trasformata non entra nel calcolo."
        )
    elif tipo == "gruppo":
        if (
            percorso.get("idMisura") in {
                "euclidean", "manhattan", "chebyshev", "minkowski", "weighted_minkowski"
            }
            and percorso.get("tipoGruppo") != "tempo"
            and interpretazione.get("riscalamentoConfermato") is True
        ):
            preelaborazione = _preelaborazione_numerica(nomi, analisi_per_nome)
            preelaborazione["descrizione"] = (
                "Le trasformazioni numeriche confermate sono applicate soltanto "
                "alle coordinate di questo gruppo."
            )
        else:
            preelaborazione = _preelaborazione_originale(
                "Il gruppo e' confrontato come un unico oggetto sui valori originali. "
                "Riscalamenti separati potrebbero modificare forma, direzione, "
                "composizione o andamento temporale."
            )
    else:
        preelaborazione = _preelaborazione_originale(
            "Il confronto separato usa la rappresentazione coerente con il significato "
            "della singola caratteristica."
        )

    compatibilita = _controlla_compatibilita_preelaborazione(
        percorso, analisi_per_nome, interpretazione, preelaborazione
    )
    mancanti = _politica_mancanti(
        nomi, analisi_per_nome, percorso, interpretazione, numero_istanze
    )
    if not mancanti["pronta"]:
        percorso["stato"] = "da_completare"
    # Il logaritmo stretto non e' compatibile con l'imputazione zero:
    # l'incompatibilita' deve apparire nel piano, non solo al calcolo.
    colonne_log = {
        passo["colonna"] for passo in preelaborazione.get("passi", [])
        if passo["metodo"] == "log"
    }
    if (
        preelaborazione.get("usaTabellaTrasformata")
        and colonne_log
        and any(nome in mancanti.get("colonne", []) for nome in colonne_log)
        and (
            (tipo == "numerico" and any(
                mancanti.get("perColonna", {}).get(nome) == "zero"
                for nome in colonne_log
            ))
            or (tipo == "gruppo" and mancanti.get("strategia") == "zero")
        )
    ):
        percorso["stato"] = "da_completare"
        percorso.setdefault("avvisi", []).append(
            "Il log(x) non è definito nello zero: sostituire un mancante "
            "con zero renderebbe impossibile la trasformazione. "
            "Scegli esclusione, confronto sulle coordinate comuni quando "
            "compatibile, oppure un'imputazione positiva giustificata."
        )
    if (
        tipo == "numerico"
        and percorso.get("idMisura") in {
            "mahalanobis", "mahalanobis_ridge", "mahalanobis_pinv"
        }
        and mancanti["presenza"]
        and any(
            strategia != "escludi_riga"
            for strategia in mancanti.get("perColonna", {}).values()
        )
    ):
        percorso["stato"] = "da_completare"
        percorso.setdefault("avvisi", []).append(
            "Le varianti di Mahalanobis stimano la covarianza su righe complete: "
            "con mancanti, scegli l'esclusione della riga per ogni colonna coinvolta. "
            "Imputazione e confronto pairwise richiederebbero una diversa stima "
            "esplicita, qui non disponibile."
        )
    percorso["preelaborazione"] = preelaborazione
    percorso["compatibilitaPreelaborazione"] = compatibilita
    percorso["origine"] = preelaborazione["etichettaOrigine"]
    percorso["mancanti"] = mancanti
    calcolabile = (
        tipo in {"gower", "numerico"}
        or percorso.get("metodo") in MISURE_SPECIALIZZATE_CALCOLABILI
        or (
            tipo == "gruppo" and percorso.get("idMisura")
            in {"euclidean", "manhattan", "chebyshev", "minkowski", "weighted_minkowski"}
        )
    ) and percorso["stato"] != "da_completare"
    percorso["calcolo"] = {
        "disponibile": calcolabile,
        "descrizione": (
            "La matrice è calcolabile nel sito."
            if calcolabile
            else "Completa le informazioni richieste prima di calcolare questo percorso."
        ),
    }
    return percorso


def _crea_percorsi(
    indipendenti: list[str],
    gruppi_con_blocco: list[tuple[dict[str, Any], dict[str, Any]]],
    ruoli: dict[str, str],
    analisi_per_nome: dict[str, dict[str, Any]],
    interpretazione: dict[str, Any],
    blocchi_per_nome: dict[str, dict[str, Any]],
    numero_istanze: int,
) -> list[dict[str, Any]]:
    """Separa il piano nei tre percorsi concordati, senza combinarne i risultati."""
    percorsi: list[dict[str, Any]] = []
    standard = [nome for nome in indipendenti if ruoli[nome] in RUOLI_GOWER]
    separati = [nome for nome in indipendenti if nome not in standard]

    # Nei CSV misti la scelta della geometria numerica resta all'utente:
    # Gower classica su tutte le caratteristiche, oppure un percorso numerico
    # distinto e un percorso Gower per le restanti caratteristiche.
    quantitative_miste = [
        nome for nome in standard
        if ruoli[nome] == "quantita"
        and analisi_per_nome[nome]["tipo"] in {"numerica", "numerica_costante"}
    ]
    altre_miste = [nome for nome in standard if nome not in quantitative_miste]
    separa_miste = (
        len(quantitative_miste) >= 2 and bool(altre_miste)
        and interpretazione.get("gestioneQuantitativeMiste") == "separato"
    )
    insiemi_standard = (
        [quantitative_miste, altre_miste] if separa_miste else [standard]
    )
    for standard in insiemi_standard:
        if not standard:
            continue
        solo_quantitative = all(
            ruoli[nome] == "quantita"
            and analisi_per_nome[nome]["tipo"] in {"numerica", "numerica_costante"}
            for nome in standard
        )
        ha_estremi = any(
            analisi_per_nome[nome].get("statistiche", {}).get("estremi", 0) > 0
            for nome in standard
        )
        stato_blocchi = "da_completare" if any(
            blocchi_per_nome[nome]["stato"] == "da_completare" for nome in standard
        ) else "pronto"

        if solo_quantitative:
            selezione = _specifica_misura_numerica(
                standard, analisi_per_nome, interpretazione, numero_istanze
            )
            stato = "da_completare" if (
                stato_blocchi == "da_completare" or selezione["stato"] == "da_completare"
            ) else "pronto"
            percorso = {
                "tipo": "numerico", "titolo": "Caratteristiche numeriche indipendenti",
                "colonne": standard,
                "motivo": (
                    "La proposta deriva dal significato attribuito agli scarti, dalla "
                    "gestione delle scale, dalla dipendenza e dai pesi delle variabili."
                ),
                "stato": stato,
                **selezione,
            }
            percorso["stato"] = stato
            percorsi.append(percorso)
        else:
            risposta_estremi = interpretazione.get("significatoEstremi", "")
            stato = stato_blocchi
            scelta_gower = interpretazione.get("tipoGowerNumeriche", "automatico")
            if ha_estremi and risposta_estremi in {"errori", "controllare"}:
                metodo = "Gower dopo il controllo dei dati"
                motivo = "Prima del calcolo occorre correggere o verificare i valori estremi segnalati."
                stato = "da_completare"
            elif scelta_gower == "robusta":
                metodo = "Dissimilarità di Gower robusta"
                motivo = (
                    "Ogni scarto numerico e' diviso per la massima distanza tra "
                    "le osservazioni confermate non anomale nella rispettiva colonna, "
                    "con saturazione a 1; le righe anomale restano nel confronto."
                )
            else:
                metodo = "Dissimilarità di Gower classica"
                motivo = "Combina quantità, categorie, livelli e variabili binarie con contributi confrontabili."
            personalizzati = any(
                ((ruoli[n] == "categoria" or (
                    ruoli[n] == "livello" and (
                        (interpretazione.get("ordinePerColonna") or {}).get(
                            n, interpretazione.get("ordineLivelli")
                        ) == "no"
                    )
                )) and (interpretazione.get("modalitaCategorieGower") or {}).get(n) == "personalizzata")
                or (ruoli[n] == "livello"
                    and (interpretazione.get("ordinePerColonna") or {}).get(
                        n, interpretazione.get("ordineLivelli")
                    ) == "si"
                    and (interpretazione.get("modalitaIntervalliGower") or {}).get(n) == "personalizzati")
                for n in standard
            )
            if personalizzati:
                metodo += " con contributi personalizzati"
                motivo += (
                    " Le dissimilarità nominali e gli intervalli ordinali "
                    "sono quelli confermati dall'utente; questa è un'estensione "
                    "di Gower, non la formulazione nominale classica."
                )
            percorsi.append({
                "tipo": "gower", "titolo": "Caratteristiche indipendenti di tipo misto",
                "colonne": standard, "metodo": metodo,
                "motivo": motivo, "stato": stato,
            })

    for nome in separati:
        blocco = blocchi_per_nome[nome]
        specifica_speciale: dict[str, Any] = {}
        if ruoli[nome] == "insieme":
            specifica_speciale = dict(
                (interpretazione.get("configurazioniInsiemi") or {}).get(nome, {})
            )
        elif ruoli[nome] == "ciclica":
            specifica_speciale = dict(
                (interpretazione.get("configurazioniCicliche") or {}).get(nome, {})
            )
        percorsi.append({
            "tipo": "separato", "titolo": ETICHETTE_RUOLO.get(ruoli[nome], "Confronto separato"),
            "colonne": [nome], "metodo": blocco["misura"],
            "motivo": blocco["motivo"], "stato": blocco["stato"],
            "parametri": specifica_speciale,
        })

    for gruppo, blocco in gruppi_con_blocco:
        percorsi.append({
            "tipo": "gruppo", "titolo": blocco["nome"], "colonne": blocco["colonne"],
            "idGruppo": gruppo.get("id"), "tipoGruppo": gruppo.get("tipo", "altro"),
            "metodo": blocco["misura"],
            "idMisura": blocco.get("idMisura"), "parametri": blocco.get("parametri", {}),
            "ordineTemporale": blocco.get("ordineTemporale"),
            "campionamentoTemporale": blocco.get("campionamentoTemporale"),
            "motivo": blocco["motivo"], "stato": blocco["stato"],
            "avvisi": list(blocco.get("avvisi", [])),
        })
    return [
        _completa_specifica_percorso(
            percorso, analisi_per_nome, interpretazione, numero_istanze
        )
        for percorso in percorsi
    ]



def _limite_teorico_percorso(percorso: dict[str, Any]) -> float | None:
    """Restituisce un limite matematico, non il massimo del campione."""
    tipo = percorso["tipo"]
    misura = percorso.get("metodo", "")
    if tipo == "gower":
        return 1.0
    if tipo == "numerico":
        if percorso.get("idMisura") == "bray_curtis":
            # Vettori non negativi: somma |a-b| <= somma(a+b).
            return 1.0
        if percorso.get("idMisura") == "canberra":
            # Ciascun addendo e' in [0,1]; il massimo teorico e' p.
            return float(len(percorso["colonne"]))
        return None
    if tipo == "separato":
        if misura in {"Uguale o diverso", "Distanza di Levenshtein normalizzata",
                      "Distanza di Hamming normalizzata",
                      "Distanza di Damerau–Levenshtein normalizzata",
                      "Dissimilarità di Jaccard tra insiemi",
                      "Dissimilarità di Dice tra insiemi",
                      "Distanza ciclica normalizzata"}:
            return 1.0
    if percorso.get("tipoGruppo") == "vettore_binario":
        return 1.0
    if misura in {
        "Dissimilarità coseno", "Dissimilarità di Pearson",
        "Dissimilarità di Spearman",
    }:
        return 2.0
    if misura in {
        "Dissimilarità di Kendall τ-b",
        "Distanza di Hellinger", "Distanza di Jensen–Shannon",
        "Dissimilarità LCSS normalizzata",
    }:
        return 1.0
    return None


def _prepara_normalizzazione_percorso(
    percorso: dict[str, Any],
    interpretazione: dict[str, Any],
    numero_righe: int,
) -> dict[str, Any]:
    """Richiede una scelta esplicita per la scala robusta; mai percentili impliciti."""
    limite = _limite_teorico_percorso(percorso)
    configurate = interpretazione.get("normalizzazioniPercorsi") or {}
    escluse_per_percorso = interpretazione.get("righeAnomaleNormalizzazione") or {}
    if not isinstance(configurate, dict) or not isinstance(escluse_per_percorso, dict):
        raise ValueError("La configurazione delle normalizzazioni non e' valida.")
    id_percorso = percorso["idPercorso"]
    metodo_default = "teorica" if limite is not None else "campionaria"
    metodo = configurate.get(id_percorso, metodo_default)
    errori: list[str] = []
    righe_escluse: list[int] = []
    if limite is not None:
        if metodo != "teorica":
            errori.append(
                "Questa misura ha un limite teorico noto: si conserva la scala "
                "naturale e non si usa una normalizzazione campionaria o robusta."
            )
    elif metodo not in {"campionaria", "robusta"}:
        errori.append("Scegli il massimo campionario oppure la scala robusta per questo percorso.")
    elif metodo == "robusta":
        testo = escluse_per_percorso.get(id_percorso, "")
        if not isinstance(testo, str) or not testo.strip():
            errori.append(
                "Per la scala robusta indica i numeri delle righe anomale del CSV "
                "(senza intestazione), separati da punto e virgola. "
                "Le righe restano nella matrice."
            )
        else:
            parti = [p for p in re.split(r"[;,\s]+", testo.strip()) if p]
            if any(not p.isdigit() or not 1 <= int(p) <= numero_righe for p in parti):
                errori.append(
                    f"I numeri delle righe anomale devono essere interi da 1 a {numero_righe}. "
                    f"Valore ricevuto: “{testo}”."
                )
            else:
                righe_escluse = sorted(int(p) for p in parti)
                if len(righe_escluse) != len(set(righe_escluse)):
                    errori.append("Ogni riga anomala deve essere elencata una volta sola.")
                if numero_righe - len(righe_escluse) < 2:
                    errori.append(
                        "Per stimare il massimo robusto servono almeno due righe non anomale."
                    )
    if errori:
        percorso["stato"] = "da_completare"
        percorso["calcolo"]["disponibile"] = False
        percorso["calcolo"]["descrizione"] = "Completa la normalizzazione di questo percorso."
        percorso.setdefault("avvisi", []).extend(errori)
    return {
        "metodo": metodo,
        "limiteTeorico": limite,
        "righeAnomale": righe_escluse,
        "valida": not errori,
        "descrizione": (
            f"Limite teorico: {format(limite, '.6g')}. Si preserva la scala naturale."
            if limite is not None else
            "Massimo campionario delle dissimilarita' valide su coppie distinte."
            if metodo == "campionaria" else
            "Massimo delle dissimilarita' tra le sole righe confermate non anomale; "
            "le altre righe restano nel confronto e possono saturare a 1."
        ),
    }





def _decodifica_vettori_binari(
    risultato: dict[str, Any], percorso: dict[str, Any],
) -> list[list[int | None] | None]:
    """Decodifica soltanto valori 0/1 o sì/no, preservando i mancanti pairwise.

    list None = intera riga non disponibile in questo blocco;
    elemento None = coordinata mancante da escludere soltanto dalla coppia.
    """
    tabella = risultato["originale"]
    nomi = percorso["colonne"]
    indici = [tabella["intestazioni"].index(nome) for nome in nomi]
    strategia = percorso["mancanti"].get("strategia", "non_necessaria")
    stati_per_colonna = percorso["mancanti"].get("statiPerColonna") or {}
    positivi = {"1", "1.0", "si", "sì", "yes", "true", "vero", "presente", "attivo"}
    negativi = {"0", "0.0", "no", "false", "falso", "assente", "inattivo"}
    vettori: list[list[int | None] | None] = []
    for numero_riga, riga in enumerate(tabella["righe"], start=1):
        if (strategia == "escludi_percorso"
                and any(
                    mancante(riga[indice]) and (
                        not stati_per_colonna or
                        stati_per_colonna.get(nome, {}).get(
                            str(riga[indice]).strip().casefold()
                        ) != "assenza"
                    )
                    for nome, indice in zip(nomi, indici)
                )):
            vettori.append(None)
            continue
        valori: list[int | None] = []
        for nome, indice in zip(nomi, indici):
            valore = riga[indice]
            if mancante(valore):
                marcatore = str(valore).strip().casefold()
                stato = stati_per_colonna.get(nome, {}).get(marcatore)
                if stati_per_colonna and stato not in STATI_MANCANTI:
                    raise ValueError(
                        f"Riga {numero_riga}, colonna “{nome}”: "
                        "specifica il significato del marcatore mancante."
                    )
                if stato == "assenza" or (
                    not stati_per_colonna and strategia == "zero"
                ):
                    valori.append(0)
                elif strategia == "pairwise":
                    valori.append(None)
                else:
                    raise ValueError(
                        f"Riga {numero_riga}, colonna “{nome}”: conferma "
                        "il significato dei valori mancanti nel vettore binario."
                    )
                continue
            stato = str(valore).strip().casefold()
            if stato in positivi:
                valori.append(1)
            elif stato in negativi:
                valori.append(0)
            else:
                raise ValueError(
                    f"Riga {numero_riga}, colonna “{nome}”: stato binario “{valore}” "
                    "non riconosciuto. Sono ammessi 0/1 e convenzioni sì/no; "
                    "non viene deciso arbitrariamente quale etichetta significhi presenza."
                )
        vettori.append(valori)
    return vettori


def _distanza_vettori_binari(
    x: list[int | None], y: list[int | None], id_misura: str,
    *, consenti_indefiniti: bool = False,
) -> float | None:
    """Distanza sulle sole coordinate osservate congiuntamente.

    Nessuna coordinata comune: None per qualunque misura.
    Jaccard per soli doppi zeri osservati: 0 (contributo valido).
    Dice per soli doppi zeri: indefinita, non va convertita in zero.
    """
    if len(x) != len(y) or not x:
        raise ValueError("I vettori binari devono avere uguale dimensione positiva.")
    if any(v is not None and v not in (0, 1) for v in [*x, *y]):
        raise ValueError("I vettori binari devono contenere soltanto 0 e 1 osservati.")
    comuni = [(a, b) for a, b in zip(x, y) if a is not None and b is not None]
    if not comuni:
        return None
    n11 = sum(a == 1 and b == 1 for a, b in comuni)
    n00 = sum(a == 0 and b == 0 for a, b in comuni)
    m = len(comuni) - n11 - n00
    if id_misura == "hamming":
        return m / len(comuni)
    if id_misura == "rogers_tanimoto":
        return 2 * m / (n11 + n00 + 2 * m)
    if id_misura == "jaccard":
        return 0.0 if n11 + m == 0 else m / (n11 + m)
    if id_misura == "dice":
        if 2 * n11 + m == 0:
            if consenti_indefiniti:
                return None
            raise ValueError(
                "Dice non è definita tra due vettori con sole assenze comuni: "
                "scegli Jaccard oppure Rogers–Tanimoto."
            )
        return m / (2 * n11 + m)
    raise ValueError(f"Misura binaria non riconosciuta: {id_misura}.")


def _verifica_vettore_binario_percorso(
    percorso: dict[str, Any], risultato: dict[str, Any],
) -> None:
    """Valida la codifica e l'esistenza di almeno un confronto locale."""
    if percorso.get("tipoGruppo") != "vettore_binario" or percorso["stato"] == "da_completare":
        return
    try:
        vettori = _decodifica_vettori_binari(risultato, percorso)
        strategia = percorso["mancanti"]["strategia"]
        validi = [v for v in vettori if v is not None]
        if strategia != "pairwise":
            if len(validi) < 2:
                raise ValueError(
                    "Servono almeno due righe complete confrontabili per il vettore binario."
                )
            if percorso["idMisura"] == "dice" and any(not any(v) for v in validi):
                raise ValueError(
                    "È presente almeno un vettore tutto zero: Dice non è definita "
                    "neppure sulla sua diagonale. Usa Jaccard, Rogers–Tanimoto "
                    "oppure escludi esplicitamente questa riga dal problema."
                )
            percorso["righeBinariValide"] = len(validi)
        else:
            # La definizione locale può essere non disponibile soltanto per
            # alcune coppie. L'aggregazione globale ne conserva la maschera.
            valide = 0
            senza_coordinate = 0
            dice_solo_assenze = 0
            for i in range(len(vettori)):
                for j in range(i + 1, len(vettori)):
                    a, b = vettori[i], vettori[j]
                    if a is None or b is None:
                        continue
                    numero_comuni = sum(
                        u is not None and v is not None for u, v in zip(a, b)
                    )
                    if numero_comuni == 0:
                        senza_coordinate += 1
                        continue
                    distanza = _distanza_vettori_binari(
                        a, b, percorso["idMisura"], consenti_indefiniti=True
                    )
                    if distanza is None:
                        dice_solo_assenze += 1
                    else:
                        valide += 1
            if valide == 0:
                raise ValueError(
                    "Non esiste alcuna coppia con contributo binario definito "
                    "sulle coordinate osservate da entrambe le righe. "
                    "Rivedi i dati, la misura o il trattamento dei mancanti."
                )
            percorso["righeBinariValide"] = sum(
                v is not None and any(s is not None for s in v) for v in vettori
            )
            percorso["coppieBinariValide"] = valide
            percorso["coppieSenzaCoordinateComuni"] = senza_coordinate
            percorso["coppieDiceIndefinite"] = dice_solo_assenze
            if senza_coordinate or dice_solo_assenze:
                percorso.setdefault("avvisi", []).append(
                    f"Il blocco binario dispone di {valide} confronti definiti; "
                    f"{senza_coordinate} coppie non condividono coordinate osservate"
                    + (
                        f" e {dice_solo_assenze} coppie hanno Dice indefinita "
                        "per sole assenze comuni."
                        if dice_solo_assenze else "."
                    )
                    + " Queste coppie non ricevono contributo dal blocco, "
                    "ma possono essere coperte da altri percorsi."
                )
    except ValueError as errore:
        percorso["stato"] = "da_completare"
        percorso["calcolo"]["disponibile"] = False
        percorso["calcolo"]["descrizione"] = "Correggi la codifica o la misura binaria."
        percorso.setdefault("avvisi", []).append(str(errore))


def _leggi_insieme_etichette(
    valore: str, specifica: dict[str, Any], politica: str,
) -> frozenset[str] | None:
    """La cella '[]' rappresenta l'insieme vuoto, la cella vuota è mancante."""
    if mancante(valore):
        if politica == "insieme_vuoto":
            return frozenset()
        if politica in {"escludi_percorso", "non_necessaria"}:
            return None
        raise ValueError("Manca una politica esplicita per le celle vuote degli insiemi.")
    if str(valore).strip() == "[]":
        return frozenset()
    separatore = specifica.get("separatore")
    if separatore not in {"|", ";", ","}:
        raise ValueError("Conferma il separatore delle etichette.")
    elementi = [v.strip() for v in str(valore).split(separatore)]
    if any(not s or s == "[]" for s in elementi):
        raise ValueError(
            "Sono presenti etichette vuote o il simbolo [] all'interno di una lista: "
            "scrivi [] soltanto per l'intero insieme vuoto; correggi i separatori consecutivi."
        )
    if specifica.get("maiuscole") == "ignora":
        elementi = [s.casefold() for s in elementi]
    elif specifica.get("maiuscole") != "distingui":
        raise ValueError("Conferma come trattare maiuscole e minuscole negli insiemi.")
    if specifica.get("ripetizioni") != "deduplica":
        raise ValueError("Conferma che le etichette ripetute contano una sola volta.")
    return frozenset(elementi)


def _distanza_insiemi(
    a: frozenset[str], b: frozenset[str], scelta: str,
) -> float:
    comuni = len(a & b)
    if scelta == "jaccard":
        totale = len(a | b)
        return 0.0 if totale == 0 else 1.0 - comuni / totale
    if scelta == "dice":
        totale = len(a) + len(b)
        return 0.0 if totale == 0 else 1.0 - 2.0 * comuni / totale
    raise ValueError("Scegli Jaccard oppure Dice per confrontare gli insiemi.")


def _distanza_ciclica(a: float, b: float, periodo: float) -> float:
    if not math.isfinite(periodo) or periodo <= 0:
        raise ValueError("Il periodo deve essere finito e strettamente positivo.")
    if not all(math.isfinite(x) and 0 <= x < periodo for x in (a, b)):
        raise ValueError("I valori ciclici devono appartenere all'intervallo [0,P).")
    ampiezza = abs(a - b)
    return 2.0 * min(ampiezza, periodo - ampiezza) / periodo


def _verifica_specializzati_percorso(
    percorso: dict[str, Any], risultato: dict[str, Any],
) -> None:
    """Controlla i domini prima di dichiarare il piano completo."""
    if percorso["tipo"] != "separato" or percorso["stato"] == "da_completare":
        return
    metodo = percorso["metodo"]
    if metodo not in {
        "Dissimilarità di Jaccard tra insiemi",
        "Dissimilarità di Dice tra insiemi",
        "Distanza ciclica normalizzata",
    }:
        return
    tabella = risultato["originale"]
    indice = tabella["intestazioni"].index(percorso["colonne"][0])
    strategia = percorso["mancanti"]["strategia"]
    specifica = percorso.get("parametri", {})
    try:
        for numero_riga, riga in enumerate(tabella["righe"], 1):
            grezzo = riga[indice]
            if metodo == "Distanza ciclica normalizzata":
                if mancante(grezzo):
                    if strategia == "escludi_percorso":
                        continue
                    raise ValueError("La cella ciclica è mancante e non è stata esclusa.")
                valore = leggi_numero(grezzo, tabella["separatore"])
                if valore is INVALIDO or valore is None:
                    raise ValueError(f"Riga {numero_riga}: non è un numero ciclico valido.")
                periodo = float(str(specifica["periodo"]).replace(",", "."))
                _distanza_ciclica(float(valore), float(valore), periodo)
            else:
                try:
                    _leggi_insieme_etichette(grezzo, specifica, strategia)
                except ValueError as errore:
                    raise ValueError(f"Riga {numero_riga}: {errore}") from errore
    except (ValueError, KeyError, TypeError) as errore:
        percorso["stato"] = "da_completare"
        percorso["calcolo"]["disponibile"] = False
        percorso["calcolo"]["descrizione"] = "Controlla il formato del blocco specializzato."
        percorso.setdefault("avvisi", []).append(str(errore))


def _verifica_distribuzione_percorso(
    percorso: dict[str, Any],
    risultato: dict[str, Any],
) -> None:
    """Controlla le distribuzioni PRIMA di autorizzare il calcolo.

    Una colonna classificata binaria può essere un bin con masse 0/1,
    ma la validità va verificata sulle righe nel loro insieme.
    """
    if percorso.get("tipoGruppo") != "distribuzione":
        return
    if percorso["stato"] == "da_completare" and (
        percorso.get("idMisura") not in {"hellinger", "jensen_shannon"}
    ):
        return
    natura = percorso.get("parametri", {}).get("natura")
    if natura not in {"probabilita", "masse"}:
        return
    tabella = risultato["originale"]
    posizioni = [tabella["intestazioni"].index(nome) for nome in percorso["colonne"]]
    strategia = percorso["mancanti"].get("strategia")
    errori = []
    valide = 0
    for numero_riga, riga in enumerate(tabella["righe"], start=1):
        raw = [leggi_numero(riga[k], tabella["separatore"]) for k in posizioni]
        if any(v is INVALIDO for v in raw):
            errori.append(f"Riga {numero_riga}: sono presenti valori non numerici.")
            continue
        if any(v is None for v in raw):
            if strategia == "escludi_percorso":
                continue
            if strategia == "zero":
                raw = [0.0 if v is None else v for v in raw]
            else:
                # La politica dei mancanti segnala già una scelta da completare.
                continue
        valori = [float(v) for v in raw]
        if any(not math.isfinite(v) or v < 0 for v in valori):
            errori.append(
                f"Riga {numero_riga}: Hellinger e Jensen–Shannon "
                "richiedono componenti finite e non negative."
            )
            continue
        totale = math.fsum(valori)
        if not math.isfinite(totale) or totale <= 0:
            errori.append(
                f"Riga {numero_riga}: la massa totale deve essere positiva. "
                "Una riga tutta nulla non definisce una distribuzione."
            )
            continue
        if natura == "probabilita" and not math.isclose(
            totale, 1.0, rel_tol=1e-6, abs_tol=1e-9
        ):
            errori.append(
                f"Riga {numero_riga}: somma {format(totale, '.9g')} diversa da 1. "
                "Se sono frequenze o percentuali, dichiarale come masse "
                "da normalizzare anziché probabilità già normalizzate."
            )
            continue
        valide += 1
    if errori:
        percorso["stato"] = "da_completare"
        percorso["calcolo"]["disponibile"] = False
        percorso["calcolo"]["descrizione"] = (
            "Correggi la distribuzione o la sua interpretazione prima del calcolo."
        )
        percorso.setdefault("avvisi", []).extend(errori[:6])
        if len(errori) > 6:
            percorso["avvisi"].append(
                f"Altre {len(errori) - 6} righe non valide."
            )
    elif valide < 2:
        percorso["stato"] = "da_completare"
        percorso["calcolo"]["disponibile"] = False
        percorso.setdefault("avvisi", []).append(
            "Restano meno di due distribuzioni valide e confrontabili."
        )
    else:
        percorso["righeDistribuzioneValide"] = valide


def _azioni_rapporto_problema(messaggio: str) -> list[str]:
    """Alternative informative: nessuna viene applicata dal software."""
    t = messaggio.casefold()
    if "covarianza" in t or "mahalanobis" in t:
        return [
            "Rivedi le colonne dipendenti o la misura selezionata.",
            "Valuta regolarizzazione o pseudoinversa soltanto dopo una scelta esplicita.",
        ]
    if "hamming" in t or "lunghezz" in t:
        return ["Verifica le lunghezze; se sono differenti, valuta Levenshtein."]
    if "peso" in t or "importanza" in t:
        return ["Conferma pesi positivi e finiti, oppure modifica la struttura dei blocchi."]
    if "mancant" in t or "vuot" in t or "non applicabil" in t:
        return [
            "Chiarisci il significato dei mancanti e scegli una strategia compatibile.",
            "Valuta esclusione delle righe o imputazione dichiarata, quando ammissibili.",
        ]
    if "estrem" in t or "anomal" in t or "outlier" in t:
        return ["Verifica i valori segnalati e conferma come trattarli prima del calcolo."]
    if "normalizz" in t or "scala" in t or "riscal" in t:
        return ["Rivedi il preprocessing o la normalizzazione di questo blocco."]
    if "colonn" in t or "grupp" in t or "blocc" in t:
        return ["Rivedi la selezione delle colonne e la loro assegnazione ai blocchi."]
    return ["Completa o modifica la scelta pertinente nel questionario o nel piano."]


def _rapporto_problemi_piano(
    avvisi_globali: list[str],
    blocchi: list[dict[str, Any]],
    percorsi: list[dict[str, Any]],
    completo: bool,
) -> dict[str, Any]:
    """Raccoglie tutti i problemi noti al piano, distinguendone l'effetto."""
    bloccanti: list[dict[str, Any]] = []
    non_bloccanti: list[dict[str, Any]] = []
    visti: set[tuple[str, str, str, str]] = set()

    def aggiungi(
        gravita: str, ambito: str, nome: str, colonne: list[str],
        messaggio: str, id_percorso: str | None = None,
    ) -> None:
        chiave = (gravita, ambito, nome, messaggio)
        if chiave in visti:
            return
        visti.add(chiave)
        destinazione = bloccanti if gravita == "bloccante" else non_bloccanti
        destinazione.append({
            "gravita": gravita,
            "ambito": ambito,
            "nome": nome,
            "idPercorso": id_percorso,
            "colonne": list(colonne),
            "messaggio": messaggio,
            "decisioniPossibili": _azioni_rapporto_problema(messaggio),
        })

    for messaggio in avvisi_globali:
        aggiungi("bloccante", "generale", "Configurazione", [], messaggio)
    for blocco in blocchi:
        gravita = "bloccante" if blocco["stato"] == "da_completare" else "avviso"
        messaggi = list(blocco.get("avvisi") or [])
        if gravita == "bloccante" and not messaggi:
            messaggi = ["La configurazione di questa caratteristica non è completa."]
        for messaggio in messaggi:
            aggiungi(gravita, "blocco", blocco["nome"],
                    blocco["colonne"], messaggio)
    for percorso in percorsi:
        gravita = "bloccante" if (
            percorso["stato"] == "da_completare" or
            not percorso["calcolo"]["disponibile"]
        ) else "avviso"
        messaggi = list(percorso.get("avvisi") or [])
        if gravita == "bloccante" and not messaggi:
            messaggi = [
                percorso["calcolo"].get("descrizione")
                or "Il percorso non è ancora calcolabile."
            ]
        for messaggio in messaggi:
            aggiungi(gravita, "percorso", percorso["titolo"],
                    percorso["colonne"], messaggio, percorso["idPercorso"])
    if not completo and not bloccanti:
        aggiungi(
            "bloccante", "generale", "Configurazione", [],
            "Il piano non è completo: rivedi le scelte prima del calcolo.",
        )
    return {
        "fase": "piano",
        "calcoloConsentito": completo,
        "numeroBloccanti": len(bloccanti),
        "numeroAvvisi": len(non_bloccanti),
        "bloccanti": bloccanti,
        "nonBloccanti": non_bloccanti,
    }


class IncompatibilitaCalcolo(ValueError):
    """Errore bloccante con un rapporto serializzabile e senza correzioni tacite."""

    def __init__(self, messaggio: str, rapporto: dict[str, Any]):
        super().__init__(messaggio)
        self.rapportoProblemi = rapporto


def _rapporto_errori_percorsi(errori: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "fase": "calcolo",
        "numeroBloccanti": len(errori),
        "numeroAvvisi": 0,
        "bloccanti": errori,
        "nonBloccanti": [],
        "coppieNonConfrontabili": [],
        "etichette": [],
        "numeroCoppieNonConfrontabili": 0,
    }


def _verifica_bray_curtis_percorso(
    percorso: dict[str, Any],
    risultato: dict[str, Any],
    interpretazione: dict[str, Any],
) -> None:
    """Richiede una convenzione per ogni confronto 0/0 di Bray--Curtis.

    Contiamo le righe realmente confrontabili DOPO il trattamento dei
    mancanti approvato, ma senza modificare i valori originali. La scelta
    è significativa solo se almeno due righe sono interamente nulle.
    """
    if (
        percorso["tipo"] != "numerico"
        or percorso.get("idMisura") != "bray_curtis"
        or percorso["stato"] == "da_completare"
    ):
        return
    try:
        vettori, indici = _righe_numeriche_per_percorso(risultato, percorso)
    except ValueError as errore:
        percorso["stato"] = "da_completare"
        percorso["calcolo"]["disponibile"] = False
        percorso["calcolo"]["descrizione"] = "Rivedi i dati numerici e i mancanti."
        percorso.setdefault("avvisi", []).append(str(errore))
        return
    righe_nulle = [
        indice + 1 for vettore, indice in zip(vettori, indici)
        if all(valore == 0 for valore in vettore)
    ]
    numero_coppie = len(righe_nulle) * (len(righe_nulle) - 1) // 2
    percorso["righeNulleBrayCurtis"] = righe_nulle
    percorso["coppieBrayDoppioZero"] = numero_coppie
    if not numero_coppie:
        return
    scelta = interpretazione.get("convenzioneBrayCurtisZero")
    if scelta not in {"zero", "indefinita"}:
        percorso["stato"] = "da_completare"
        percorso["calcolo"]["disponibile"] = False
        percorso["calcolo"]["descrizione"] = (
            "Scegli come interpretare i confronti Bray–Curtis tra due vettori nulli."
        )
        percorso.setdefault("avvisi", []).append(
            f"Bray–Curtis produce 0/0 in {numero_coppie} coppie di righe "
            "interamente nulle: scegli esplicitamente se attribuire "
            "dissimilarità zero oppure lasciare il confronto non definito."
        )
        return
    percorso.setdefault("parametri", {})["doppioZero"] = scelta
    if scelta == "zero":
        percorso.setdefault("avvisi", []).append(
            f"Convenzione confermata: le {numero_coppie} coppie Bray–Curtis "
            "(0,0) hanno dissimilarità zero e sono contributi validi."
        )
    else:
        percorso.setdefault("avvisi", []).append(
            f"Le {numero_coppie} coppie Bray–Curtis (0,0) restano non definite "
            "per scelta esplicita. La matrice finale richiede altri contributi "
            "validi per ciascuna di esse."
        )


def crea_piano_confronto(risultato: dict[str, Any], interpretazione: dict[str, Any]) -> dict[str, Any]:
    """Costruisce un piano verificabile senza calcolare ancora le distanze."""
    if not isinstance(interpretazione, dict):
        raise ValueError("Le risposte del questionario non sono valide.")
    profili = risultato["questionario"]["colonne"]
    analisi_per_nome = {colonna["nome"]: colonna for colonna in risultato["colonne"]}
    risposte_colonne = interpretazione.get("colonne", {})
    assegnazioni = interpretazione.get("assegnazioni", {})
    gruppi = interpretazione.get("gruppi", [])
    if not isinstance(risposte_colonne, dict) or not isinstance(assegnazioni, dict):
        raise ValueError("Le risposte sulle colonne e le assegnazioni devono essere oggetti validi.")
    if (
        not isinstance(gruppi, list)
        or not all(isinstance(gruppo, dict) and isinstance(gruppo.get("id"), str)
                   and gruppo["id"].strip() for gruppo in gruppi)
    ):
        raise ValueError("Ogni gruppo deve avere un identificativo testuale non vuoto.")
    gruppi_per_id = {gruppo["id"]: gruppo for gruppo in gruppi}
    if len(gruppi_per_id) != len(gruppi):
        raise ValueError("I gruppi devono avere identificativi distinti.")
    incluse: list[str] = []
    ruoli: dict[str, str] = {}
    for profilo in profili:
        risposta = risposte_colonne.get(profilo["nome"], {})
        if risposta.get("usa", profilo["usaNelConfronto"]):
            incluse.append(profilo["nome"])
        ruoli[profilo["nome"]] = risposta.get("ruolo", profilo["ruoloSuggerito"])

    indipendenti = [
        nome for nome in incluse
        if not assegnazioni.get(nome) or assegnazioni.get(nome) not in gruppi_per_id
    ]
    blocchi_indipendenti = [
        _blocco_indipendente(nome, ruoli[nome], analisi_per_nome[nome], interpretazione)
        for nome in indipendenti
    ]
    blocchi = list(blocchi_indipendenti)
    gruppi_con_blocco: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for gruppo in gruppi:
        membri = [nome for nome in incluse if assegnazioni.get(nome) == gruppo.get("id")]
        if membri:
            blocco = _blocco_gruppo(gruppo, membri, analisi_per_nome, interpretazione, ruoli)
            blocchi.append(blocco)
            gruppi_con_blocco.append((gruppo, blocco))

    blocchi_per_nome = {blocco["nome"]: blocco for blocco in blocchi_indipendenti}
    diagnosi = crea_diagnosi_decisionale(
        incluse, indipendenti, ruoli, analisi_per_nome, bool(gruppi_con_blocco)
    )
    percorsi = _crea_percorsi(
        indipendenti, gruppi_con_blocco, ruoli, analisi_per_nome,
        interpretazione, blocchi_per_nome, len(risultato["originale"]["righe"]),
    )
    colonne_percorso = [nome for percorso in percorsi for nome in percorso["colonne"]]
    if len(colonne_percorso) != len(set(colonne_percorso)):
        raise ValueError("Una colonna non puo' appartenere a due percorsi di confronto.")
    for indice, percorso in enumerate(percorsi, start=1):
        percorso["idPercorso"] = f"percorso-{indice}"
    for percorso in percorsi:
        _verifica_distribuzione_percorso(percorso, risultato)
        _verifica_vettore_binario_percorso(percorso, risultato)
        _verifica_serie_a_coppie_percorso(percorso, risultato)
        _verifica_specializzati_percorso(percorso, risultato)
        _verifica_bray_curtis_percorso(percorso, risultato, interpretazione)
    # Hamming richiede che tutte le sequenze confrontabili abbiano una
    # lunghezza comune. Il controllo precede il calcolo; non si converte
    # implicitamente a Levenshtein se le lunghezze sono differenti.
    for percorso in percorsi:
        if percorso["tipo"] != "separato" or percorso["metodo"] != "Distanza di Hamming normalizzata":
            continue
        nome = percorso["colonne"][0]
        indice = risultato["originale"]["intestazioni"].index(nome)
        strategia = percorso["mancanti"].get("strategia")
        stringhe = [
            "" if mancante(riga[indice]) else str(riga[indice]).strip()
            for riga in risultato["originale"]["righe"]
            if not mancante(riga[indice]) or strategia == "stringa_vuota"
        ]
        lunghezze = {len(valore) for valore in stringhe}
        if len(lunghezze) > 1:
            percorso["stato"] = "da_completare"
            percorso["calcolo"]["disponibile"] = False
            percorso["calcolo"]["descrizione"] = "Hamming richiede uguale lunghezza per le sequenze confrontate."
            percorso.setdefault("avvisi", []).append(
                f"La colonna “{nome}” presenta sequenze di lunghezza differente "
                f"({', '.join(map(str, sorted(lunghezze)))} caratteri). "
                "Per Hamming devono avere tutte uguale lunghezza: "
                "se interessano inserimenti o cancellazioni, seleziona Levenshtein."
            )
        elif stringhe:
            percorso["lunghezzaSequenzeHamming"] = len(stringhe[0])

    # La configurazione completa di Gower viene verificata prima di
    # dichiarare il piano pronto, non soltanto quando si avvia il calcolo.
    for percorso in percorsi:
        if percorso["tipo"] != "gower":
            continue
        try:
            metadati = _metadati_gower(risultato, interpretazione, percorso)
            costanti = [v["nome"] for v in metadati if v["costante"]]
            percorso["colonneCostantiGower"] = costanti
            percorso["colonneEscluseGower"] = []
            percorso["pesiGower"] = {v["nome"]: v["peso"] for v in metadati}
            mancanti_risolti = {v["nome"]: v["politicaMancanti"] for v in metadati
                                if analisi_per_nome[v["nome"]]["mancanti"] > 0}
            if mancanti_risolti:
                etichette = {
                    "escludi": "esclusi a coppie",
                    "assenza": "trattati come assenza",
                    "zero": "sostituiti esplicitamente con zero",
                    "codifiche": "trattati singolarmente secondo i simboli confermati",
                }
                percorso["mancanti"]["strategia"] = (
                    "esclusione_pairwise" if set(mancanti_risolti.values()) == {"escludi"}
                    else "configurazione_per_colonna"
                )
                percorso["mancanti"]["descrizione"] = (
                    "Per Gower: " + "; ".join(
                        nome + ": " + etichette[politica]
                        for nome, politica in mancanti_risolti.items()
                    ) + ". Le coppie senza alcun contributo disponibile restano non definite."
                )
            if costanti:
                percorso.setdefault("avvisi", []).append(
                    "Colonne costanti mantenute con contributo zero e peso positivo: " +
                    ", ".join(costanti) + "."
                )
        except ValueError as errore:
            percorso["stato"] = "da_completare"
            percorso["calcolo"]["disponibile"] = False
            percorso["calcolo"]["descrizione"] = "Completa la configurazione di Gower."
            percorso.setdefault("avvisi", []).append(str(errore))

    avvisi: list[str] = []
    # Un'assegnazione rimasta dopo l'eliminazione di un gruppo non può
    # trasformarsi tacitamente in un confronto indipendente. Il piano
    # resta visibile per la correzione, ma il calcolo è bloccato.
    for nome in incluse:
        id_richiesto = assegnazioni.get(nome)
        if id_richiesto and id_richiesto not in gruppi_per_id:
            avvisi.append(
                f"La colonna “{nome}” è assegnata al gruppo inesistente "
                f"“{id_richiesto}”. Riassegnala a un gruppo presente oppure "
                "conferma che debba essere indipendente, togliendo l'assegnazione."
            )
    standard_indipendenti = [
        nome for nome in indipendenti if ruoli[nome] in RUOLI_GOWER
    ]
    quantitative_indipendenti = [
        nome for nome in standard_indipendenti
        if ruoli[nome] == "quantita"
        and analisi_per_nome[nome]["tipo"] in {"numerica", "numerica_costante"}
    ]
    altre_standard = [
        nome for nome in standard_indipendenti if nome not in quantitative_indipendenti
    ]
    if len(quantitative_indipendenti) >= 2 and altre_standard:
        scelta_miste = interpretazione.get("gestioneQuantitativeMiste")
        if scelta_miste not in {"gower", "separato"}:
            avvisi.append(
                "Decidi se confrontare tutte le caratteristiche indipendenti "
                "con Gower oppure confrontare le quantità con una misura numerica "
                "in un blocco separato. Nessuna struttura viene scelta automaticamente."
            )
        elif scelta_miste == "separato":
            diagnosi["proposta"] = {
                "idMisura": "blocchi_misti",
                "misura": "Blocchi distinti: quantitativo e Gower",
                "politicaPreelaborazione": "specifica_del_percorso",
                "motivo": (
                    "Le quantità indipendenti formano un blocco con la misura "
                    "numerica selezionata; le altre caratteristiche standard "
                    "formano un blocco Gower. I due contributi normalizzati "
                    "vengono aggregati con pesi positivi in una sola matrice."
                ),
            }
            diagnosi["conferma"] = ""
    if not interpretazione.get("riga"):
        avvisi.append("Indica che cosa rappresenta ogni riga.")
    if not blocchi:
        avvisi.append("Includi almeno una colonna nel confronto.")
    if interpretazione.get("significatoMancanti") in {None, "", "ignoto"}:
        specifiche_mancanti = interpretazione.get("mancantiPerColonna") or {}
        if any(
            analisi_per_nome[n]["mancanti"] > 0
            and specifiche_mancanti.get(n) not in {"escludi", "assenza", "zero"}
            for n in incluse
        ):
            avvisi.append("Indica che cosa significano le caselle vuote nelle colonne incluse.")

    pesi_percorsi = interpretazione.get("pesiPercorsi") or {}
    if not isinstance(pesi_percorsi, dict):
        pesi_percorsi = {}
        avvisi.append("La configurazione dell’importanza dei percorsi non è valida.")
    modalita_pesi = interpretazione.get("modalitaPesiPercorsi")
    if modalita_pesi in (None, ""):
        # Compatibilità: le risposte storiche che indicano direttamente
        # pesiPercorsi mantengono il loro esatto significato manuale.
        modalita_pesi = "personalizzati" if pesi_percorsi else "uguali"
    if modalita_pesi not in {"uguali", "dimensione", "personalizzati"}:
        avvisi.append(
            "La modalità dei pesi globali non è riconosciuta: scegli uguali, "
            "numero di caratteristiche del blocco oppure personalizzati."
        )
    dimensioni_blocchi: dict[str, int] = {}
    for percorso in percorsi:
        id_percorso = percorso["idPercorso"]
        # |B_k| conta le colonne sorgente disgiunte attribuite al percorso,
        # NON il numero di righe, categorie distinte, campioni osservati,
        # né i singoli contributi interni di una misura non additiva.
        dimensione = len(percorso["colonne"])
        dimensioni_blocchi[id_percorso] = dimensione
        if dimensione == 0:
            percorso["stato"] = "da_completare"
            percorso["calcolo"]["disponibile"] = False
            percorso.setdefault("avvisi", []).append(
                "Non si può attribuire un peso proporzionale a un blocco senza colonne."
            )
        if modalita_pesi == "dimensione":
            grezzo = dimensione
        elif modalita_pesi == "personalizzati":
            grezzo = pesi_percorsi.get(id_percorso, 1)
        else:
            grezzo = 1
        try:
            peso = float(str(grezzo).strip().replace(",", "."))
        except (TypeError, ValueError):
            peso = math.nan
        if not math.isfinite(peso) or peso <= 0:
            percorso["stato"] = "da_completare"
            percorso["calcolo"]["disponibile"] = False
            percorso.setdefault("avvisi", []).append(
                "L’importanza del percorso deve essere un numero strettamente positivo."
            )
            peso = 1.0
        percorso["numeroCaratteristiche"] = dimensione
        percorso["pesoAggregazione"] = peso
        percorso["originePesoAggregazione"] = (
            "Numero di colonne sorgente del blocco"
            if modalita_pesi == "dimensione" else
            "Peso positivo indicato dall'utente"
            if modalita_pesi == "personalizzati" else
            "Peso unitario per blocco"
        )
        percorso["normalizzazione"] = _prepara_normalizzazione_percorso(
            percorso, interpretazione, len(risultato["originale"]["righe"])
        )
    pesatura_globale = {
        "modalita": modalita_pesi,
        "dimensioniBlocchi": dimensioni_blocchi,
        "descrizione": (
            "Proposta esplicita w_k=|B_k|: il peso di ogni percorso è il "
            "numero delle sue colonne sorgente disgiunte. Non equivale "
            "in generale a pesare equamente ogni elemento o misura interna, "
            "soprattutto per gruppi composti e dissimilarità non additive."
            if modalita_pesi == "dimensione" else
            "Pesi positivi personalizzati per ciascun blocco, senza "
            "modificare gli eventuali pesi interni alla misura."
            if modalita_pesi == "personalizzati" else
            "Un peso positivo unitario per blocco, indipendentemente "
            "da quante colonne lo compongono."
        ),
    }
    incluse_con_estremi = any(analisi_per_nome[n].get("statistiche", {}).get("estremi", 0) > 0 for n in incluse)
    incluse_con_candidati_multivariati = any(
        percorso["tipo"] == "numerico"
        and percorso.get("diagnosiAutomatica", {}).get(
            "diagnosiMultivariata", {}
        ).get("numeroCandidati", 0) > 0
        for percorso in percorsi
    )
    if (incluse_con_estremi or incluse_con_candidati_multivariati) and interpretazione.get("significatoEstremi") in {None, "", "ignoto"}:
        avvisi.append("Indica se i valori molto lontani dagli altri sono plausibili.")
    elif (incluse_con_estremi or incluse_con_candidati_multivariati) and interpretazione.get("significatoEstremi") in {"errori", "controllare"}:
        avvisi.append("Controlla i valori estremi prima di calcolare le distanze.")

    diagnostica_mancanti, avvisi_mancanti = _diagnostica_stati_mancanti(
        risultato, interpretazione, incluse, ruoli, assegnazioni,
        gruppi_per_id, percorsi,
    )
    avvisi.extend(avvisi_mancanti)

    for percorso in percorsi:
        if not percorso["mancanti"]["pronta"]:
            colonne = ", ".join(percorso["mancanti"]["colonne"])
            avvisi.append(
                f"Definisci la strategia operativa per i valori mancanti nel percorso "
                f"“{percorso['titolo']}” ({colonne})."
            )

    completo = (
        bool(blocchi)
        and not avvisi
        and all(b["stato"] != "da_completare" for b in blocchi)
        and all(p["stato"] != "da_completare" for p in percorsi)
    )
    # Anteprima esattamente della rappresentazione che il piano numerico usa.
    anteprima_numerica = None
    if completo and len(percorsi) == 1 and percorsi[0]["tipo"] == "numerico":
        percorso = percorsi[0]
        if percorso["preelaborazione"]["usaTabellaTrasformata"]:
            metodi = {passo["colonna"]: passo["metodo"]
                      for passo in percorso["preelaborazione"]["passi"]}
            righe_preparate, _ = _righe_numeriche_per_percorso(risultato, percorso)
            anteprima_numerica = {
                "colonne": percorso["colonne"],
                "metodi": metodi,
                "righe": righe_preparate[:12],
            }
    return {
        "anteprimaNumerica": anteprima_numerica,
        "rapportoProblemi": _rapporto_problemi_piano(avvisi, blocchi, percorsi, completo),
        "diagnosticaMancantiSemantici": diagnostica_mancanti,
        "pesaturaGlobale": pesatura_globale,
        "diagnosi": diagnosi, "blocchi": blocchi, "percorsi": percorsi, "avvisi": avvisi,
        "completo": completo, "conteggioBlocchi": len(blocchi),
        "conteggioPercorsi": len(percorsi), "versioneContratto": 4,
    }


def _leggi_data(valore: Any) -> float | None:
    if mancante(valore):
        return None
    testo = str(valore).strip()
    formati = (
        "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d",
        "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M",
    )
    for formato in formati:
        try:
            data = dt.datetime.strptime(testo, formato).replace(tzinfo=dt.timezone.utc)
            return data.timestamp()
        except ValueError:
            pass
    raise ValueError(f"Il valore “{testo}” non è una data riconosciuta.")


def _etichette_righe(risultato: dict[str, Any], interpretazione: dict[str, Any]) -> list[str]:
    n = len(risultato["originale"]["righe"])
    profili = risultato["questionario"]["colonne"]
    risposte = interpretazione.get("colonne", {})
    candidati = [
        profilo["nome"] for profilo in profili
        if risposte.get(profilo["nome"], {}).get("ruolo", profilo["ruoloSuggerito"]) == "identificativo"
    ]
    if candidati:
        nome = candidati[0]
        indice = risultato["originale"]["intestazioni"].index(nome)
        valori = [str(riga[indice]).strip() for riga in risultato["originale"]["righe"]]
        if all(valore and not mancante(valore) for valore in valori) and len(set(valori)) == n:
            return valori
    return [f"Riga {indice + 1}" for indice in range(n)]


def _politica_mancanti_gower(
    nome: str, ruolo: str, ha_mancanti: bool, interpretazione: dict[str, Any]
) -> str:
    """Rende operativa la risposta sui mancanti senza inventare zeri numerici."""
    if not ha_mancanti:
        return "escludi"
    if interpretazione.get("significatoMancanti") == "misto":
        if ruolo not in {"presenza", "binaria", "categoria", "quantita", "livello", "data"}:
            raise ValueError(
                f"Il ruolo “{ruolo}” della colonna “{nome}” non è supportato in Gower."
            )
        return "codifiche"
    specifiche = interpretazione.get("mancantiPerColonna") or {}
    if not isinstance(specifiche, dict):
        raise ValueError("Le risposte sui mancanti per colonna non sono valide.")
    risposta = specifiche.get(nome)
    if risposta in ("escludi", "assenza", "zero"):
        politica = risposta
    else:
        globale = interpretazione.get("significatoMancanti", "")
        if globale in ("sconosciuto", "non_applicabile"):
            politica = "escludi"
        elif globale == "assenza":
            politica = "assenza"
        else:
            raise ValueError(
                f"Specifica come trattare le caselle vuote della colonna “{nome}”."
            )
    if politica == "zero" and ruolo != "quantita":
        raise ValueError(
            f"Per la colonna “{nome}”, sostituire i mancanti con zero è ammesso solo "
            "per quantità numeriche e richiede una scelta esplicita."
        )
    if politica == "assenza" and ruolo not in {"presenza", "binaria", "categoria"}:
        raise ValueError(
            f"La colonna “{nome}” non è una presenza o una categoria: "
            "non si può interpretare automaticamente una casella vuota come assenza. "
            "Scegli «escludi» oppure, per una quantità, conferma esplicitamente lo zero."
        )
    return politica


def _valori_binari_gower(
    grezzi: list[str], nome: str, ruolo: str, politica: str,
    interpretazione: dict[str, Any], asimmetrica: bool,
    *, forza_decodifica: bool = False,
) -> list[str | int | None]:
    """Per i binari asimmetrici determina la polarità, senza supporre A/B = 0/1."""
    distinti = sorted({str(v).strip() for v in grezzi if not mancante(v)})
    if not distinti:
        return [0 if politica == "assenza" else None for _ in grezzi]
    if len(distinti) > 2:
        raise ValueError(
            f"La colonna “{nome}” ha {len(distinti)} stati osservati: "
            "non può essere trattata come binaria."
        )
    configurati = interpretazione.get("presenzaPositivaPerColonna") or {}
    if not isinstance(configurati, dict):
        raise ValueError("La configurazione degli stati di presenza non è valida.")
    positivo = configurati.get(nome, "")
    if positivo and positivo not in distinti:
        raise ValueError(
            f"Il valore indicato come presenza per “{nome}” non compare nella colonna."
        )
    if not positivo:
        convenzioni_positive = {"1", "si", "sì", "yes", "true", "vero", "presente", "attivo"}
        convenzioni_negative = {"0", "no", "false", "falso", "assente", "inattivo"}

        def polarita_testuale(valore: str) -> int | None:
            testo = valore.casefold()
            if testo in convenzioni_positive:
                return 1
            if testo in convenzioni_negative:
                return 0
            try:
                numero = float(testo.replace(",", "."))
            except ValueError:
                return None
            return int(numero) if numero in (0, 1) else None

        candidati = [v for v in distinti if polarita_testuale(v) == 1]
        altri = [v for v in distinti if polarita_testuale(v) == 0]
        if len(candidati) == 1 and len(candidati) + len(altri) == len(distinti):
            positivo = candidati[0]
        elif len(distinti) == 1 and polarita_testuale(distinti[0]) == 0:
            # Per una colonna tutta di assenze, nessuna presenza è osservata.
            positivo = None

    if (asimmetrica or politica == "assenza" or forza_decodifica) and positivo == "":
        raise ValueError(
            f"Per la colonna “{nome}” scegli quale stato indica la presenza. "
            "Non è possibile ricavarlo automaticamente da queste etichette."
        )
    if not (asimmetrica or politica == "assenza" or forza_decodifica):
        return [None if mancante(v) else str(v).strip() for v in grezzi]
    return [
        0 if mancante(v) and politica == "assenza" else
        None if mancante(v) else
        (1 if str(v).strip() == positivo else 0)
        for v in grezzi
    ]



def _categorie_nominali_gower(
    nome: str,
    valori: list[Any],
    interpretazione: dict[str, Any],
) -> dict[frozenset[Any], float] | None:
    """Contributi simmetrici personalizzati, diagonale implicitamente nulla.

    Le coppie sono indicate una sola volta (triangolo superiore), in
    ordine alfabetico delle etichette osservate; l'assenza confermata
    compare dopo le categorie effettive, come sentinella distinta.
    Non si impone la disuguaglianza triangolare a una dissimilarita'.
    """
    modi = interpretazione.get("modalitaCategorieGower") or {}
    if not isinstance(modi, dict):
        raise ValueError("Le modalità di confronto delle categorie non sono valide.")
    modalita = modi.get(nome, "semplice")
    if modalita == "semplice":
        return None
    if modalita != "personalizzata":
        raise ValueError(f"Per “{nome}” scegli confronto uguale/diverso o dissimilarità personalizzate.")
    categorie = sorted({
        str(v) for v in valori if v is not None and v is not ASSENZA_GOWER
    })
    if any(v is ASSENZA_GOWER for v in valori):
        categorie.append(ASSENZA_GOWER)
    if len(categorie) <= 1:
        return {}
    if len(categorie) > 16:
        raise ValueError(
            f"Per “{nome}” sono presenti {len(categorie)} categorie. "
            "L'editor personalizzato supporta fino a 16 stati; "
            "riduci gli stati o usa il confronto uguale/diverso."
        )
    configurazioni = interpretazione.get("dissimilaritaCategorieGower") or {}
    if not isinstance(configurazioni, dict):
        raise ValueError("La configurazione delle dissimilarità categoriali non è valida.")
    configurazione = configurazioni.get(nome)
    etichette = [None if v is ASSENZA_GOWER else v for v in categorie]
    if not isinstance(configurazione, dict) or configurazione.get("livelli") != etichette:
        raise ValueError(
            f"Per “{nome}” completa la tabella delle dissimilarità fra "
            "tutte le categorie osservate, compresa l'eventuale assenza confermata."
        )
    coppie = configurazione.get("coppie")
    if not isinstance(coppie, dict):
        raise ValueError(f"Per “{nome}” manca la tabella delle dissimilarità.")
    richieste = {
        f"{i}:{j}" for i in range(len(categorie))
        for j in range(i + 1, len(categorie))
    }
    if set(coppie) != richieste:
        raise ValueError(
            f"Per “{nome}” assegna una dissimilarità a ogni coppia distinta "
            "di categorie, senza valori mancanti o aggiuntivi."
        )
    risultato: dict[frozenset[Any], float] = {}
    for i in range(len(categorie)):
        for j in range(i + 1, len(categorie)):
            chiave = f"{i}:{j}"
            testo = coppie[chiave]
            try:
                valore = float(str(testo).strip().replace(",", "."))
            except (TypeError, ValueError):
                raise ValueError(
                    f"Per “{nome}” il confronto {etichette[i]}–{etichette[j]} "
                    "deve essere un numero compreso tra 0 e 1."
                ) from None
            if not math.isfinite(valore) or not 0 <= valore <= 1:
                raise ValueError(
                    f"Per “{nome}” il confronto {etichette[i]}–{etichette[j]} "
                    "deve essere finito e compreso tra 0 e 1."
                )
            risultato[frozenset((categorie[i], categorie[j]))] = valore
    return risultato


def _posizioni_ordinali_gower(
    nome: str,
    livelli: list[Any],
    interpretazione: dict[str, Any],
) -> dict[Any, float]:
    """Scala cumulativa con incrementi positivi, sempre in [0,1]."""
    modi = interpretazione.get("modalitaIntervalliGower") or {}
    if not isinstance(modi, dict):
        raise ValueError("Le modalità dei livelli ordinali non sono valide.")
    modalita = modi.get(nome, "equidistanti")
    if modalita == "equidistanti":
        return {
            livello: i / max(1, len(livelli) - 1)
            for i, livello in enumerate(livelli)
        }
    if modalita != "personalizzati":
        raise ValueError(
            f"Per “{nome}” scegli livelli equidistanti oppure intervalli personalizzati."
        )
    if len(livelli) <= 1:
        return {livello: 0.0 for livello in livelli}
    grezzi = interpretazione.get("passiOrdinaliGower") or {}
    if not isinstance(grezzi, dict):
        raise ValueError("Gli intervalli ordinali non sono configurati correttamente.")
    testo = grezzi.get(nome, "")
    if not isinstance(testo, str) or not testo.strip():
        raise ValueError(
            f"Per “{nome}” indica {len(livelli) - 1} ampiezze positive, "
            "una per ogni intervallo tra livelli consecutivi, separate da ';'."
        )
    parti = [v.strip() for v in testo.split(";")]
    if len(parti) != len(livelli) - 1:
        raise ValueError(
            f"Per “{nome}” servono esattamente {len(livelli) - 1} "
            "ampiezze positive, separate da punto e virgola."
        )
    try:
        incrementi = [float(v.replace(",", ".")) for v in parti]
    except ValueError:
        raise ValueError(
            f"Per “{nome}” le ampiezze devono essere numeri positivi."
        ) from None
    if any(not math.isfinite(v) or v <= 0 for v in incrementi):
        raise ValueError(
            f"Per “{nome}” gli intervalli tra livelli consecutivi "
            "devono essere finiti e strettamente positivi."
        )
    totale = math.fsum(incrementi)
    if not math.isfinite(totale) or totale <= 0:
        raise ValueError(
            f"Per “{nome}” la somma delle ampiezze non è finita e positiva."
        )
    posizioni = {livelli[0]: 0.0}
    accumulato = 0.0
    for i, passo in enumerate(incrementi, start=1):
        accumulato += passo
        posizioni[livelli[i]] = (
            1.0 if i == len(livelli) - 1 else accumulato / totale
        )
    return posizioni


def _metadati_gower(
    risultato: dict[str, Any],
    interpretazione: dict[str, Any],
    percorso: dict[str, Any],
) -> list[dict[str, Any]]:
    """Prepara tutti i contributi, incluse le colonne costanti con peso positivo."""
    tabella = risultato["originale"]
    analisi_per_nome = {colonna["nome"]: colonna for colonna in risultato["colonne"]}
    profili = {profilo["nome"]: profilo for profilo in risultato["questionario"]["colonne"]}
    risposte = interpretazione.get("colonne", {})
    robusta = percorso["metodo"].startswith("Dissimilarità di Gower robusta")
    righe_outlier = interpretazione.get("righeOutlierGower") or {}
    if not isinstance(righe_outlier, dict):
        raise ValueError("La selezione delle righe anomale per Gower non e' valida.")
    numero_zeri_esclusi = 0
    pesi_configurati = interpretazione.get("pesiGower") or {}
    if not isinstance(pesi_configurati, dict):
        raise ValueError("I pesi di Gower devono essere specificati per colonna.")
    metadati: list[dict[str, Any]] = []

    for nome in percorso["colonne"]:
        grezzi = [riga[tabella["intestazioni"].index(nome)] for riga in tabella["righe"]]
        ruolo = risposte.get(nome, {}).get("ruolo", profili[nome]["ruoloSuggerito"])
        analisi = analisi_per_nome[nome]
        try:
            peso = float(str(pesi_configurati.get(nome, "1")).strip().replace(",", "."))
        except (ValueError, TypeError):
            raise ValueError(f"Il peso Gower della colonna “{nome}” deve essere positivo.")
        if not math.isfinite(peso) or peso <= 0:
            raise ValueError(
                f"Il peso Gower della colonna “{nome}” deve essere strettamente positivo."
            )
        politica = _politica_mancanti_gower(
            nome, ruolo, any(mancante(v) for v in grezzi), interpretazione
        )
        asimmetrica = ruolo == "presenza" and (
            (interpretazione.get("zeriCondivisiPerColonna") or {}).get(
                nome, interpretazione.get("zeriCondivisi")
            ) == "no"
        )
        if ruolo in {"presenza", "binaria"}:
            if ruolo == "presenza" and (
                (interpretazione.get("zeriCondivisiPerColonna") or {}).get(
                    nome, interpretazione.get("zeriCondivisi")
                ) not in {"si", "no"}
            ):
                raise ValueError(
                    f"Per la colonna “{nome}” conferma se contano le assenze condivise."
                )
            codifiche_binarie = (
                [
                    "0" if mancante(v) and _stato_mancante_dichiarato(
                        v, nome, interpretazione
                    ) == "assenza"
                    else "" if mancante(v) else v
                    for v in grezzi
                ] if politica == "codifiche" else grezzi
            )
            forza_binario = politica == "codifiche" and any(
                mancante(v) and _stato_mancante_dichiarato(
                    v, nome, interpretazione
                ) == "assenza" for v in grezzi
            )
            valori = _valori_binari_gower(
                codifiche_binarie, nome, ruolo,
                "escludi" if politica == "codifiche" else politica,
                interpretazione, asimmetrica, forza_decodifica=forza_binario,
            )
            tipo, scala, limita = "nominale", None, False
        elif ruolo == "quantita":
            if politica == "codifiche":
                for v in grezzi:
                    if (mancante(v) and _stato_mancante_dichiarato(
                        v, nome, interpretazione
                    ) == "assenza"):
                        raise ValueError(
                            f"Per “{nome}” l'assenza non diventa zero numerico: "
                            "indica un valore realmente misurato nel CSV oppure "
                            "cambia la codifica del marcatore."
                        )
            numeri = [leggi_numero(v, tabella["separatore"]) for v in grezzi]
            if any(v is INVALIDO for v in numeri):
                raise ValueError(f"La colonna “{nome}” contiene quantità non numeriche.")
            valori = [
                0.0 if v is None and politica == "zero" else v
                for v in numeri
            ]
            osservati = [float(v) for v in valori if v is not None]
            intervallo = max(osservati) - min(osservati) if osservati else 0.0
            if robusta:
                # La decisione e' sempre esplicita e specifica per colonna.
                # I numeri sono indici di riga nel CSV, a partire da 1,
                # esclusi soltanto dalla STIMA della scala, non dalla matrice.
                grezzo_esclusi = righe_outlier.get(nome, "")
                if not isinstance(grezzo_esclusi, str):
                    raise ValueError(
                        f"Per la colonna “{nome}” indica i numeri delle righe "
                        "anomale separati da punto e virgola."
                    )
                parti = [v for v in re.split(r"[;,\s]+", grezzo_esclusi.strip()) if v]
                if any(not v.isdigit() or int(v) < 1 or int(v) > len(grezzi) for v in parti):
                    raise ValueError(
                        f"Per “{nome}” le righe anomale devono essere numeri "
                        f"interi compresi tra 1 e {len(grezzi)}."
                    )
                esclusi = {int(v) - 1 for v in parti}
                non_anomali = [
                    float(v) for indice, v in enumerate(valori)
                    if v is not None and indice not in esclusi
                ]
                numero_zeri_esclusi += len(esclusi)
                if intervallo > 0 and (
                    len(non_anomali) < 2 or max(non_anomali) == min(non_anomali)
                ):
                    raise ValueError(
                        f"Per “{nome}” la scala robusta non e' definibile: "
                        "le righe non anomale devono includere almeno due "
                        "valori distinti. Rivedi gli outlier oppure scegli Gower classica."
                    )
                scala = max(non_anomali) - min(non_anomali) if non_anomali else 0.0
            else:
                scala = intervallo
            tipo, limita = "numerica", robusta
        elif ruolo == "data":
            valori = [_leggi_data(v) for v in grezzi]
            osservati = sorted({v for v in valori if v is not None})
            if interpretazione.get("usoDate") == "ordine":
                posizioni = {v: i / max(1, len(osservati) - 1) for i, v in enumerate(osservati)}
                valori = [None if v is None else posizioni[v] for v in valori]
                scala = 1.0
            else:
                scala = osservati[-1] - osservati[0] if osservati else 0.0
            tipo, limita = "numerica", False
        elif ruolo == "livello":
            risposta = (interpretazione.get("ordinePerColonna") or {}).get(
                nome, interpretazione.get("ordineLivelli")
            )
            if risposta not in {"si", "no"}:
                raise ValueError(f"Conferma se la colonna “{nome}” è ordinata.")
            if risposta == "no":
                valori = [None if mancante(v) else str(v).strip() for v in grezzi]
                tipo, scala, limita = "nominale", None, False
            else:
                osservati = [str(v).strip() for v in grezzi if not mancante(v)]
                numeri = [leggi_numero(v, tabella["separatore"]) for v in osservati]
                if all(v is not INVALIDO and v is not None for v in numeri):
                    livelli = sorted({float(v) for v in numeri})
                    mappa = _posizioni_ordinali_gower(nome, livelli, interpretazione)
                    valori = [
                        None if mancante(v) else mappa[float(leggi_numero(v, tabella["separatore"]))]
                        for v in grezzi
                    ]
                else:
                    testo_ordine = (interpretazione.get("ordiniLivelliGower") or {}).get(nome, "")
                    livelli = [val.strip() for val in testo_ordine.split(";") if val.strip()]
                    if len(set(livelli)) != len(livelli) or set(livelli) != set(osservati):
                        raise ValueError(
                            f"Specifica per “{nome}” tutti e soli i livelli in ordine, "
                            "separati da punto e virgola."
                        )
                    mappa = _posizioni_ordinali_gower(nome, livelli, interpretazione)
                    valori = [None if mancante(v) else mappa[str(v).strip()] for v in grezzi]
                tipo, scala, limita = "numerica", 1.0, False
        else:
            valori = [
                ASSENZA_GOWER if mancante(v) and (
                    politica == "assenza" or (
                        politica == "codifiche"
                        and _stato_mancante_dichiarato(v, nome, interpretazione) == "assenza"
                    )
                ) else
                None if mancante(v) else str(v).strip()
                for v in grezzi
            ]
            tipo, scala, limita = "nominale", None, False

        distanze_nominali = (
            _categorie_nominali_gower(nome, valori, interpretazione)
            if tipo == "nominale" and ruolo in {"categoria", "livello"}
            else None
        )

        # Decisioni 7 e 19: una colonna costante resta nel denominatore
        # per ogni coppia in cui e' effettivamente osservata, con distanza zero.
        # Una colonna interamente mancante NON e' una costante osservata.
        distinti = {v for v in valori if v is not None}
        metadati.append({
            "nome": nome, "tipo": tipo, "valori": valori, "scala": scala,
            "limita": limita, "asimmetrica": asimmetrica, "peso": peso,
            "costante": len(distinti) == 1,
            "politicaMancanti": politica,
            "distanzeNominali": distanze_nominali,
        })

    if robusta and not numero_zeri_esclusi:
        raise ValueError(
            "Per Gower robusta seleziona esplicitamente le righe anomale "
            "da escludere dalla stima della scala in almeno una colonna quantitativa; "
            "in alternativa scegli Gower classica."
        )
    if not metadati:
        raise ValueError("Nessuna caratteristica e' stata inclusa nel confronto Gower.")
    return metadati


def _media_pesata_stabile(
    termini: list[tuple[float, float]],
) -> float | None:
    """Media con pesi finiti positivi, senza overflow del denominatore.

    w/max(w) preserva il rapporto tra i pesi in aritmetica reale.
    Un termine di peso positivo e distanza zero resta nel denominatore.
    None indica esclusivamente l'assenza di TUTTI i contributi.
    """
    if not termini:
        return None
    if any(not math.isfinite(w) or w <= 0 for w, _ in termini):
        raise ValueError("Ogni contributo richiede un peso finito strettamente positivo.")
    if any(not math.isfinite(d) for _, d in termini):
        raise ValueError("Ogni contributo deve avere una dissimilarita' finita.")
    massimo = max(w for w, _ in termini)
    relativi = [w / massimo for w, _ in termini]
    totale = math.fsum(relativi)
    if totale <= 0:
        raise ValueError("La somma dei pesi positivi non e' rappresentabile.")
    return math.fsum(r * d for r, (_, d) in zip(relativi, termini)) / totale


def calcola_matrice_gower(risultato: dict[str, Any], interpretazione: dict[str, Any]) -> dict[str, Any]:
    piano = crea_piano_confronto(risultato, interpretazione)
    if not piano["completo"]:
        raise ValueError("Completa le informazioni richieste prima di calcolare la matrice.")
    percorsi = [percorso for percorso in piano["percorsi"] if percorso["tipo"] == "gower"]
    if not percorsi:
        raise ValueError("Il piano non contiene un percorso di Gower.")
    percorso = percorsi[0]
    metadati = _metadati_gower(risultato, interpretazione, percorso)
    n = len(risultato["originale"]["righe"])
    matrice: list[list[float | None]] = [[0.0 for _ in range(n)] for _ in range(n)]

    for i in range(n):
        for k in range(i + 1, n):
            contributi_validi: list[tuple[float, float]] = []
            assenze_condivise_osservate = False
            for variabile in metadati:
                a = variabile["valori"][i]
                b = variabile["valori"][k]
                if a is None or b is None:
                    continue
                if variabile.get("costante"):
                    # Perfino una presenza sempre assente e' un blocco costante
                    # confermato: il suo contributo e' nullo ma il peso rimane.
                    contributo = 0.0
                elif variabile["tipo"] == "nominale":
                    if variabile.get("asimmetrica") and float(a) == 0 and float(b) == 0:
                        # Nessun peso positivo per una co-assenza isolata in
                        # Gower; ma se entrambi gli insiemi di presenze sono
                        # vuoti, la convenzione Jaccard della decisione 36
                        # attribuisce distanza zero, non valore mancante.
                        assenze_condivise_osservate = True
                        continue
                    if a == b:
                        contributo = 0.0
                    elif variabile.get("distanzeNominali") is not None:
                        contributo = variabile["distanzeNominali"][frozenset((a, b))]
                    else:
                        contributo = 1.0
                else:
                    scala = variabile["scala"]
                    contributo = 0.0 if scala == 0 else abs(float(a) - float(b)) / scala
                    if variabile.get("limita"):
                        contributo = min(contributo, 1.0)
                contributi_validi.append((variabile["peso"], contributo))
            distanza = _media_pesata_stabile(contributi_validi)
            if distanza is None and assenze_condivise_osservate:
                distanza = 0.0
            matrice[i][k] = distanza
            matrice[k][i] = distanza

    etichette = _etichette_righe(risultato, interpretazione)
    righe_csv = [[etichetta, *riga] for etichetta, riga in zip(etichette, matrice)]
    nota = (
        "Per le quantita', Gower robusta usa il massimo scarto tra i valori "
        "confermati non anomali, con contributi limitati a 1; le righe anomale "
        "rimangono nella matrice."
        if percorso["metodo"].startswith("Dissimilarità di Gower robusta")
        else "Per le quantità, Gower classica divide lo scarto per l’intervallo osservato."
    )
    costanti = [v["nome"] for v in metadati if v["costante"]]
    if costanti:
        nota += " Colonne costanti mantenute con peso positivo e dissimilarita' zero: " + ", ".join(costanti) + "."
    personalizzate = [
        v["nome"] for v in metadati if v.get("distanzeNominali") is not None
    ]
    if personalizzate:
        nota += (
            " Categorie con dissimilarità personalizzate: "
            + ", ".join(personalizzate)
            + ". Dati simmetrici in [0,1], diagonale nulla; "
            "non è garantita la disuguaglianza triangolare."
        )
    ordinali_personalizzati = [
        v["nome"] for v in metadati
        if (interpretazione.get("modalitaIntervalliGower") or {}).get(v["nome"])
        == "personalizzati"
    ]
    if ordinali_personalizzati:
        nota += (
            " Livelli ordinali con intervalli personalizzati: "
            + ", ".join(ordinali_personalizzati)
            + ". Gli scarti sono differenze di posizioni cumulative normalizzate."
        )
    nota += " I pesi positivi sono applicati sia al numeratore sia al denominatore."
    return {
        "metodo": percorso["metodo"], "colonne": percorso["colonne"],
        "etichette": etichette, "matrice": matrice,
        "indiciRighe": list(range(n)), "limiteAggregazione": 1.0,
        "csv": crea_csv(["Riga", *etichette], righe_csv), "nota": nota,
    }


def _trasforma_per_percorso(
    valore: Any,
    analisi: dict[str, Any],
    metodo: str,
) -> float | None:
    """Applica esattamente la trasformazione dichiarata nel piano numerico."""
    numero = leggi_numero(valore, analisi["separatore"])
    if numero is None:
        return None
    if numero is INVALIDO:
        raise ValueError(f"La colonna “{analisi['nome']}” contiene valori non numerici.")
    numero = float(numero)
    stats = analisi.get("statistiche", {})
    if metodo in {"nessuno", "originale"}:
        return numero
    if metodo == "costante" or (
        stats.get("deviazione") == 0 and metodo not in {"log", "log1p"}
    ):
        return 0.0
    if metodo == "zscore":
        return (numero - stats["media"]) / stats["deviazione"]
    if metodo == "robusto":
        if stats.get("iqr", 0) == 0:
            raise ValueError(f"La scala robusta non è definita per la colonna “{analisi['nome']}”.")
        return (numero - stats["mediana"]) / stats["iqr"]
    if metodo == "minmax":
        ampiezza = stats["massimo"] - stats["minimo"]
        return 0.0 if ampiezza == 0 else (numero - stats["minimo"]) / ampiezza
    if metodo == "maxabs":
        return 0.0 if stats.get("massimoAssoluto", 0) == 0 else numero / stats["massimoAssoluto"]
    if metodo == "log":
        if numero <= 0:
            raise ValueError(
                f"La trasformazione log(x) richiede valori strettamente positivi "
                f"(x>0) nella colonna “{analisi['nome']}”. "
                "La trasformazione non aggiunge costanti implicite."
            )
        return math.log(numero)
    if metodo == "log1p":
        if numero < 0:
            raise ValueError(
                f"La trasformazione log(1+x) richiede numeri non negativi "
                f"nella colonna “{analisi['nome']}”."
            )
        return math.log1p(numero)
    raise ValueError(f"Trasformazione numerica non riconosciuta: {metodo}.")


def _righe_numeriche_per_percorso(
    risultato: dict[str, Any],
    percorso: dict[str, Any],
) -> tuple[list[list[float]], list[int]]:
    """Applica esclusioni, imputazioni e trasformazioni dichiarate nel piano."""
    nomi = percorso["colonne"]
    tabella = risultato["originale"]
    analisi_per_nome = {colonna["nome"]: colonna for colonna in risultato["colonne"]}
    indici = [tabella["intestazioni"].index(nome) for nome in nomi]
    metodi = {
        passo["colonna"]: passo["metodo"]
        for passo in percorso["preelaborazione"]["passi"]
    }
    strategie = percorso.get("mancanti", {}).get("perColonna", {})
    righe_numeriche: list[list[float | None]] = []
    indici_usati: list[int] = []

    for indice_riga, riga in enumerate(tabella["righe"]):
        if any(
            mancante(riga[indice]) and strategie.get(nome) == "escludi_riga"
            for nome, indice in zip(nomi, indici)
        ):
            continue
        vettore: list[float | None] = []
        for nome, indice in zip(nomi, indici):
            grezzo: Any = riga[indice]
            if mancante(grezzo):
                strategia = strategie.get(nome, "")
                stats = analisi_per_nome[nome].get("statistiche", {})
                if strategia == "imputa_mediana":
                    grezzo = stats.get("mediana")
                elif strategia == "imputa_media":
                    grezzo = stats.get("media")
                elif strategia == "zero":
                    grezzo = 0.0
                elif strategia == "pairwise":
                    vettore.append(None)
                    continue
                else:
                    raise ValueError(
                        f"Scegli come trattare il valore mancante nella colonna “{nome}”."
                    )
            valore = _trasforma_per_percorso(
                grezzo, analisi_per_nome[nome], metodi.get(nome, "nessuno")
            )
            if valore is None:
                raise ValueError(
                    f"Il valore mancante nella colonna “{nome}” non è stato risolto."
                )
            vettore.append(valore)
        righe_numeriche.append(vettore)
        indici_usati.append(indice_riga)

    if len(righe_numeriche) < 2:
        raise ValueError(
            "Dopo la gestione dei mancanti restano meno di due righe confrontabili."
        )
    return righe_numeriche, indici_usati


def _cholesky(matrice: list[list[float]]) -> list[list[float]]:
    p = len(matrice)
    scala = max((abs(v) for riga in matrice for v in riga), default=1.0)
    tolleranza = scala * 1e-12
    l = [[0.0] * p for _ in range(p)]
    for i in range(p):
        for j in range(i + 1):
            somma = matrice[i][j] - sum(l[i][k] * l[j][k] for k in range(j))
            if i == j:
                if somma <= tolleranza:
                    raise ValueError("La matrice di covarianza non è definita positiva.")
                l[i][j] = math.sqrt(somma)
            else:
                l[i][j] = somma / l[j][j]
    return l


def _covarianza(
    righe: list[list[float]], richiede_rango_pieno: bool = True,
) -> list[list[float]]:
    n = len(righe)
    if n < 2 or not righe or not righe[0]:
        raise ValueError("La covarianza richiede almeno due righe complete e una colonna.")
    p = len(righe[0])
    if any(len(riga) != p or any(not math.isfinite(v) for v in riga) for riga in righe):
        raise ValueError("La covarianza richiede vettori completi e finiti.")
    if richiede_rango_pieno and n <= p:
        raise ValueError("Per Mahalanobis classica servono più righe complete delle colonne.")
    medie = [sum(riga[j] for riga in righe) / n for j in range(p)]
    return [[
        sum((riga[j] - medie[j]) * (riga[k] - medie[k]) for riga in righe) / (n - 1)
        for k in range(p)
    ] for j in range(p)]




def _spettro_covarianza(matrice: list[list[float]]) -> list[tuple[float, list[float]]]:
    """Autovalori e autovettori ortonormali di una matrice simmetrica, via Jacobi.

    Non sostituisce gli autovalori minimi con numeri positivi: l'eventuale
    troncamento è separato e dipende dalla soglia dichiarata dall'utente.
    """
    n = len(matrice)
    if not 1 <= n <= 60 or any(len(riga) != n for riga in matrice):
        raise ValueError("La pseudoinversa supporta da 1 a 60 coordinate numeriche.")
    a = [[float(v) for v in riga] for riga in matrice]
    if any(not math.isfinite(v) for riga in a for v in riga):
        raise ValueError("La covarianza contiene valori non finiti.")
    scala = max(abs(v) for riga in a for v in riga)
    if any(abs(a[i][j] - a[j][i]) > 1e-12 * scala
           for i in range(n) for j in range(i)):
        raise ValueError("La covarianza non è simmetrica.")
    if scala == 0:
        return [(0.0, [float(i == j) for i in range(n)]) for j in range(n)]
    v = [[float(i == j) for j in range(n)] for i in range(n)]
    for _ in range(60 * n * n):
        pivot = max(((abs(a[i][j]), i, j) for i in range(n)
                     for j in range(i + 1, n)), default=(0.0, 0, 0))
        off, i, j = pivot
        if off <= scala * 1e-14:
            break
        alpha = a[i][i]
        beta = a[j][j]
        tau = (beta - alpha) / (2.0 * a[i][j])
        t = (1.0 if tau >= 0 else -1.0) / (abs(tau) + math.hypot(1.0, tau))
        c = 1.0 / math.hypot(1.0, t)
        s = t * c
        a[i][i] = alpha - t * a[i][j]
        a[j][j] = beta + t * a[i][j]
        a[i][j] = a[j][i] = 0.0
        for k in range(n):
            if k != i and k != j:
                aki, akj = a[k][i], a[k][j]
                a[k][i] = a[i][k] = c * aki - s * akj
                a[k][j] = a[j][k] = s * aki + c * akj
            vki, vkj = v[k][i], v[k][j]
            v[k][i] = c * vki - s * vkj
            v[k][j] = s * vki + c * vkj
    else:
        raise ValueError("La diagonalizzazione della covarianza non è convergente.")
    autovalori = [(a[j][j], [v[i][j] for i in range(n)]) for j in range(n)]
    limite = max(1e-12 * scala, 0.0)
    if any(valore < -limite for valore, _ in autovalori):
        raise ValueError("La covarianza ha autovalori negativi oltre la tolleranza numerica.")
    return [(max(0.0, valore), vec) for valore, vec in autovalori]


def _prepara_covarianza_mahalanobis(
    righe: list[list[float]], id_misura: str, parametri: dict[str, Any],
) -> dict[str, Any]:
    """Prepara una sola matrice di covarianza su righe complete.

    Sλ = S + λI, λ > 0 (λ nelle unità quadratiche dei valori originali).
    S+ = V diag(1/μj per μj > ε μmax, 0 altrimenti) V^T.
    Nessuna delle due opzioni è scelta implicitamente.
    """
    if id_misura not in {"mahalanobis", "mahalanobis_ridge", "mahalanobis_pinv"}:
        raise ValueError("Variante di Mahalanobis non riconosciuta.")
    cov = _covarianza(righe, richiede_rango_pieno=id_misura == "mahalanobis")
    n = len(cov)
    if id_misura == "mahalanobis_pinv":
        tol = float(parametri["tolleranzaRelativa"])
        if not math.isfinite(tol) or not 1e-12 <= tol <= 0.1:
            raise ValueError("La soglia relativa per la pseudoinversa non è valida.")
        spettro = _spettro_covarianza(cov)
        massimo = max(valore for valore, _ in spettro)
        selezionati = [(valore, v) for valore, v in spettro
                       if massimo > 0 and valore > tol * massimo]
        return {
            "autodirezioni": selezionati,
            "rangoEffettivo": len(selezionati),
            "dimensione": n,
            "tolleranzaRelativa": tol,
            "numeroRigheCovarianza": len(righe),
        }
    if id_misura == "mahalanobis_ridge":
        lam = float(parametri["lambda"])
        if not math.isfinite(lam) or lam <= 0:
            raise ValueError("La regolarizzazione richiede λ finito e strettamente positivo.")
        cov = [[v + (lam if i == j else 0.0) for j, v in enumerate(riga)]
               for i, riga in enumerate(cov)]
        inversa = _inversa_gauss_jordan(cov)
        if inversa is None:
            raise ValueError("La regolarizzazione è numericamente troppo piccola: aumenta λ.")
        cond = _norma_infinito_matrice(cov) * _norma_infinito_matrice(inversa)
        if not math.isfinite(cond) or cond > 1e8:
            raise ValueError(
                "La covarianza regolarizzata resta mal condizionata: "
                "aumenta λ oppure modifica le colonne."
            )
        return {
            "cholesky": _cholesky(cov),
            "lambda": lam,
            "condizionamento": cond,
            "dimensione": n,
            "numeroRigheCovarianza": len(righe),
        }
    return {
        "cholesky": _cholesky(cov),
        "dimensione": n,
        "numeroRigheCovarianza": len(righe),
    }


def _distanza_coordinate_comuni(
    x: list[float | None],
    y: list[float | None],
    id_misura: str,
    parametri: dict[str, Any],
) -> float | None:
    """Confronta SOLO coordinate osservate da entrambe le righe.

    Minkowski (anche euclidea e Manhattan) usa
        (sum_{l in O} a_l |x_l-y_l|^q / sum_{l in O} a_l)^(1/q).
    Le coordinate non osservate non contribuiscono e i pesi non si
    redistribuiscono su indici differenti. Con O vuoto: None.
    """
    if len(x) != len(y):
        raise ValueError("I vettori devono avere la stessa dimensione.")
    supportate = {
        "euclidean", "manhattan", "minkowski", "weighted_minkowski",
        "chebyshev", "weighted_chebyshev",
    }
    if id_misura not in supportate:
        raise ValueError(
            f"Il confronto pairwise non e' disponibile per la misura {id_misura}."
        )
    pesata = id_misura in {"weighted_minkowski", "weighted_chebyshev"}
    if pesata:
        pesi = [float(v) for v in parametri.get("pesi", [])]
        if len(pesi) != len(x) or any(not math.isfinite(v) or v <= 0 for v in pesi):
            raise ValueError("Occorre un peso finito e strettamente positivo per coordinata.")
    else:
        pesi = [1.0] * len(x)
    comuni = [i for i, (a, b) in enumerate(zip(x, y))
              if a is not None and b is not None]
    if not comuni:
        return None
    if any(not math.isfinite(float(x[i])) or not math.isfinite(float(y[i]))
           for i in comuni):
        raise ValueError("Le coordinate comuni devono essere numeri finiti.")
    if id_misura in {"chebyshev", "weighted_chebyshev"}:
        return max(pesi[i] * abs(float(x[i]) - float(y[i])) for i in comuni)
    q = (
        1.0 if id_misura == "manhattan"
        else 2.0 if id_misura == "euclidean"
        else float(parametri.get("q", 2))
    )
    if not math.isfinite(q) or q < 1:
        raise ValueError("L'esponente di Minkowski deve essere finito e almeno 1.")
    somma_pesi = sum(pesi[i] for i in comuni)
    return (
        sum(pesi[i] * abs(float(x[i]) - float(y[i])) ** q for i in comuni)
        / somma_pesi
    ) ** (1 / q)


def _distanza_numerica(
    x: list[float],
    y: list[float],
    id_misura: str,
    parametri: dict[str, Any],
    cholesky_covarianza: list[list[float]] | None = None,
    autodirezioni: list[tuple[float, list[float]]] | None = None,
) -> float | None:
    scarti = [abs(a - b) for a, b in zip(x, y)]
    if id_misura == "manhattan":
        return sum(scarti)
    if id_misura == "euclidean":
        return math.sqrt(sum(scarto**2 for scarto in scarti))
    if id_misura == "chebyshev":
        return max(scarti, default=0.0)
    if id_misura == "minkowski":
        q = float(parametri["q"])
        return sum(scarto**q for scarto in scarti) ** (1 / q)
    if id_misura == "weighted_minkowski":
        q = float(parametri["q"])
        pesi = [float(peso) for peso in parametri["pesi"]]
        return sum(peso * scarto**q for peso, scarto in zip(pesi, scarti)) ** (1 / q)
    if id_misura == "weighted_chebyshev":
        pesi = [float(peso) for peso in parametri["pesi"]]
        return max((peso * scarto for peso, scarto in zip(pesi, scarti)), default=0.0)
    if id_misura == "standardized_euclidean":
        scale = [float(scala) for scala in parametri["scale"]]
        return math.sqrt(sum((scarto / scala) ** 2 for scarto, scala in zip(scarti, scale)))
    if id_misura == "mahalanobis_pinv":
        if autodirezioni is None:
            raise ValueError("La pseudoinversa della covarianza non è disponibile.")
        differenze = [a - b for a, b in zip(x, y)]
        return math.sqrt(sum(
            (sum(v * d for v, d in zip(vettore, differenze)) ** 2) / autovalore
            for autovalore, vettore in autodirezioni
        ))
    if id_misura in {"mahalanobis", "mahalanobis_ridge"}:
        if cholesky_covarianza is None:
            raise ValueError("La covarianza necessaria per Mahalanobis non è disponibile.")
        differenze = [a - b for a, b in zip(x, y)]
        z: list[float] = []
        for i, differenza in enumerate(differenze):
            residuo = differenza - sum(cholesky_covarianza[i][k] * z[k] for k in range(i))
            z.append(residuo / cholesky_covarianza[i][i])
        return math.sqrt(sum(valore**2 for valore in z))
    if id_misura == "canberra":
        return sum(
            0.0 if abs(a) + abs(b) == 0 else abs(a - b) / (abs(a) + abs(b))
            for a, b in zip(x, y)
        )
    if id_misura == "bray_curtis":
        denominatore = math.fsum(a + b for a, b in zip(x, y))
        if denominatore == 0:
            # 0/0 non e' una distanza definita. L'estensione a zero
            # richiede la conferma esplicita nel piano di confronto.
            return 0.0 if parametri.get("doppioZero") == "zero" else None
        return math.fsum(scarti) / denominatore
    if id_misura == "chi_square":
        return math.sqrt(sum(
            0.0 if a + b == 0 else (a - b) ** 2 / (a + b)
            for a, b in zip(x, y)
        ))
    raise ValueError(f"Misura numerica non riconosciuta: {id_misura}.")


def calcola_matrice_numerica(
    risultato: dict[str, Any],
    interpretazione: dict[str, Any],
) -> dict[str, Any]:
    piano = crea_piano_confronto(risultato, interpretazione)
    if not piano["completo"]:
        raise ValueError("Completa le informazioni richieste prima di calcolare la matrice.")
    percorsi = [percorso for percorso in piano["percorsi"] if percorso["tipo"] == "numerico"]
    if len(percorsi) != 1:
        raise ValueError("Il piano non contiene un unico percorso numerico calcolabile.")
    percorso = percorsi[0]
    nomi = percorso["colonne"]
    tabella = risultato["originale"]
    if len(tabella["righe"]) > 1000:
        raise ValueError("La matrice completa è limitata a 1000 righe per evitare di bloccare il browser.")
    analisi_per_nome = {colonna["nome"]: colonna for colonna in risultato["colonne"]}
    righe_numeriche, indici_usati = _righe_numeriche_per_percorso(risultato, percorso)

    id_misura = percorso["idMisura"]
    parametri = dict(percorso.get("parametri", {}))
    if id_misura == "standardized_euclidean":
        parametri["scale"] = [analisi_per_nome[nome]["statistiche"]["deviazione"] for nome in nomi]
    fattore_cholesky = None
    autodirezioni = None
    diagnostica_covarianza = None
    if id_misura in {"mahalanobis", "mahalanobis_ridge", "mahalanobis_pinv"}:
        diagnostica_covarianza = _prepara_covarianza_mahalanobis(
            righe_numeriche, id_misura, parametri
        )
        fattore_cholesky = diagnostica_covarianza.get("cholesky")
        autodirezioni = diagnostica_covarianza.get("autodirezioni")

    n = len(righe_numeriche)
    matrice: list[list[float | None]] = [[0.0 for _ in range(n)] for _ in range(n)]
    usa_pairwise = "pairwise" in percorso.get("mancanti", {}).get("perColonna", {}).values()
    for i in range(n):
        for k in range(i + 1, n):
            distanza = (
                _distanza_coordinate_comuni(
                    righe_numeriche[i], righe_numeriche[k], id_misura, parametri
                ) if usa_pairwise else
                _distanza_numerica(
                    righe_numeriche[i], righe_numeriche[k],
                    id_misura, parametri, fattore_cholesky, autodirezioni
                )
            )
            matrice[i][k] = distanza
            matrice[k][i] = distanza

    tutte_le_etichette = _etichette_righe(risultato, interpretazione)
    etichette = [tutte_le_etichette[indice] for indice in indici_usati]
    righe_csv = [[etichetta, *riga] for etichetta, riga in zip(etichette, matrice)]
    origine = percorso["preelaborazione"]["etichettaOrigine"].lower()
    nota = f"Calcolata sulle colonne {', '.join(nomi)} usando {origine}."
    if percorso["mancanti"]["presenza"]:
        nota += " " + percorso["mancanti"]["descrizione"]
        escluse = len(tabella["righe"]) - len(righe_numeriche)
        if escluse:
            nota += f" Righe escluse: {escluse}."
    if id_misura == "bray_curtis" and percorso.get("coppieBrayDoppioZero", 0):
        nota += (
            " Convenzione per due vettori nulli: dissimilarità zero "
            "(contributo definito)." if parametri.get("doppioZero") == "zero" else
            " Due vettori nulli: confronto non definito, disponibile soltanto "
            "quando altri blocchi forniscono contributi."
        )
    if id_misura == "mahalanobis":
        nota += " La covarianza empirica considera il pattern con cui le colonne variano insieme; nessuna colonna è stata eliminata."
    elif id_misura == "mahalanobis_ridge":
        nota += (
            " Mahalanobis regolarizzata: Sλ = S + λI, "
            f"λ = {format(parametri['lambda'], '.12g')}, "
            f"condizionamento infinito stimato {format(diagnostica_covarianza['condizionamento'], '.6g')}. "
            "λ è riferito alle unità al quadrato delle coordinate originali."
        )
    elif id_misura == "mahalanobis_pinv":
        nota += (
            " Mahalanobis con pseudoinversa di Moore–Penrose da "
            f"{diagnostica_covarianza['numeroRigheCovarianza']} righe complete; "
            f"rango numerico {diagnostica_covarianza['rangoEffettivo']}/{diagnostica_covarianza['dimensione']}; "
            f"soglia relativa {format(parametri['tolleranzaRelativa'], '.12g')}. "
            "Le direzioni con autovalori sotto soglia sono ignorate: "
            "sullo spazio completo può essere una pseudometrica."
        )
    return {
        "diagnosticaCovarianza": (
            {chiave: valore for chiave, valore in diagnostica_covarianza.items()
             if chiave not in {"autodirezioni", "cholesky"}}
            if diagnostica_covarianza is not None else None
        ),
        "metodo": percorso["metodo"], "colonne": nomi,
        "etichette": etichette, "matrice": matrice,
        "indiciRighe": indici_usati,
        "limiteAggregazione": _limite_teorico_percorso(percorso),
        "csv": crea_csv(["Riga", *etichette], righe_csv), "nota": nota,
    }


def _ranghi_medi(valori: list[float]) -> list[float]:
    ordinati = sorted(range(len(valori)), key=lambda indice: valori[indice])
    ranghi = [0.0] * len(valori)
    posizione = 0
    while posizione < len(ordinati):
        fine = posizione + 1
        while fine < len(ordinati) and valori[ordinati[fine]] == valori[ordinati[posizione]]:
            fine += 1
        rango = (posizione + 1 + fine) / 2
        for indice in ordinati[posizione:fine]:
            ranghi[indice] = rango
        posizione = fine
    return ranghi


def _correlazione_pearson(x: list[float], y: list[float]) -> float | None:
    media_x = sum(x) / len(x)
    media_y = sum(y) / len(y)
    centrati_x = [valore - media_x for valore in x]
    centrati_y = [valore - media_y for valore in y]
    norma_x = math.sqrt(sum(valore**2 for valore in centrati_x))
    norma_y = math.sqrt(sum(valore**2 for valore in centrati_y))
    if norma_x == 0 or norma_y == 0:
        return None
    correlazione = sum(a * b for a, b in zip(centrati_x, centrati_y)) / (norma_x * norma_y)
    return max(-1.0, min(1.0, correlazione))


def _levenshtein_normalizzata(a: str, b: str) -> float:
    if not a and not b:
        return 0.0
    precedente = list(range(len(b) + 1))
    for indice_a, carattere_a in enumerate(a, start=1):
        corrente = [indice_a]
        for indice_b, carattere_b in enumerate(b, start=1):
            corrente.append(min(
                corrente[-1] + 1,
                precedente[indice_b] + 1,
                precedente[indice_b - 1] + (carattere_a != carattere_b),
            ))
        precedente = corrente
    return precedente[-1] / max(len(a), len(b))



def _damerau_levenshtein_normalizzata(a: str, b: str) -> float:
    """Damerau–Levenshtein completa, non Optimal String Alignment.

    Il costo minimo è diviso per max(len(a),len(b)). Per due stringhe
    vuote la dissimilarità è posta a zero, come per Levenshtein.
    """
    n, m = len(a), len(b)
    if not max(n, m):
        return 0.0
    infinito = n + m
    matrice = [[0] * (m + 2) for _ in range(n + 2)]
    matrice[0][0] = infinito
    for i in range(n + 1):
        matrice[i + 1][0] = infinito
        matrice[i + 1][1] = i
    for j in range(m + 1):
        matrice[0][j + 1] = infinito
        matrice[1][j + 1] = j
    ultima_riga: dict[str, int] = {}
    for i in range(1, n + 1):
        ultima_colonna = 0
        for j in range(1, m + 1):
            i1 = ultima_riga.get(b[j - 1], 0)
            j1 = ultima_colonna
            costo = int(a[i - 1] != b[j - 1])
            if costo == 0:
                ultima_colonna = j
            matrice[i + 1][j + 1] = min(
                matrice[i][j] + costo,
                matrice[i + 1][j] + 1,
                matrice[i][j + 1] + 1,
                matrice[i1][j1] + (i - i1 - 1) + 1 + (j - j1 - 1),
            )
        ultima_riga[a[i - 1]] = i
    return matrice[n + 1][m + 1] / max(n, m)


def _hamming_normalizzata(a: str, b: str) -> float:
    """Quota delle posizioni discordanti in sequenze di lunghezza identica."""
    if len(a) != len(b):
        raise ValueError(
            "La distanza di Hamming richiede sequenze con uguale numero "
            "di caratteri. Se la lunghezza differisce, scegli Levenshtein."
        )
    if not a:
        return 0.0
    return sum(x != y for x, y in zip(a, b)) / len(a)


def _kendall_tau_b(x: list[float], y: list[float]) -> float | None:
    """Kendall tau-b con conteggi di concordanze, discordanze e pari merito.

    Le coppie in parita' su entrambe le serie non contribuiscono.
    Denominatore nullo: correlazione matematicamente non definita.
    """
    if len(x) != len(y) or len(x) < 2:
        return None
    concordanti = discordanti = pari_solo_x = pari_solo_y = 0
    for i in range(len(x)):
        for j in range(i + 1, len(x)):
            dx = x[i] - x[j]
            dy = y[i] - y[j]
            if dx == 0 and dy == 0:
                continue
            if dx == 0:
                pari_solo_x += 1
            elif dy == 0:
                pari_solo_y += 1
            elif dx * dy > 0:
                concordanti += 1
            else:
                discordanti += 1
    denominatore = math.sqrt(
        (concordanti + discordanti + pari_solo_x)
        * (concordanti + discordanti + pari_solo_y)
    )
    if denominatore == 0:
        return None
    return max(-1.0, min(1.0, (concordanti - discordanti) / denominatore))






def _interpreta_coppie_temporali(
    descrizione: str, colonne: list[str],
) -> list[list[str]]:
    """Appaiamento dichiarato dall'utente, senza inferenza dalle intestazioni."""
    if not isinstance(descrizione, str) or not descrizione.strip():
        raise ValueError(
            "Indica le coppie in ordine come tempo1:valore1; tempo2:valore2, "
            "includendo tutte e sole le colonne del gruppo."
        )
    parti = [s.strip() for s in descrizione.split(";")]
    coppie = [[nome.strip() for nome in parte.split(":")] for parte in parti]
    if len(coppie) < 2 or any(
        len(coppia) != 2 or any(not nome for nome in coppia) for coppia in coppie
    ) or len(coppie) * 2 != len(colonne):
        raise ValueError(
            "Servono almeno due coppie tempo:valore, separate da punto e virgola."
        )
    usate = [nome for coppia in coppie for nome in coppia]
    if len(set(usate)) != len(usate) or set(usate) != set(colonne):
        raise ValueError(
            "Ogni colonna del gruppo deve comparire esattamente una volta, "
            "come tempo o valore: correggi le coppie duplicate o mancanti."
        )
    return coppie


def _serie_da_coppie(
    tabella: dict[str, Any], percorso: dict[str, Any],
) -> list[dict[str, list[float]] | None]:
    """Serie univariate con tempi individuali. Nessuna imputazione tacita."""
    coppie = percorso.get("parametri", {}).get("coppie", [])
    strategia = percorso["mancanti"]["strategia"]
    indici = {nome: i for i, nome in enumerate(tabella["intestazioni"])}
    if len(coppie) < 2:
        raise ValueError("Non sono state confermate almeno due coppie tempo-valore.")
    serie: list[dict[str, list[float]] | None] = []
    for numero_riga, riga in enumerate(tabella["righe"], 1):
        tempi: list[float] = []
        valori: list[float] = []
        esclusa = False
        for nome_t, nome_v in coppie:
            t_raw, v_raw = riga[indici[nome_t]], riga[indici[nome_v]]
            manca_t, manca_v = mancante(t_raw), mancante(v_raw)
            if manca_t or manca_v:
                if strategia == "escludi_percorso":
                    esclusa = True
                    break
                if manca_t and manca_v and strategia == "salta_slot":
                    continue
                if manca_t != manca_v:
                    raise ValueError(
                        f"Riga {numero_riga}, coppia {nome_t}:{nome_v}: "
                        "manca solo il timestamp o solo il valore. "
                        "Correggi il CSV oppure escludi esplicitamente l'intera serie."
                    )
                raise ValueError(
                    f"Riga {numero_riga}: conferma la politica per le coppie vuote."
                )
            t = leggi_numero(t_raw, tabella["separatore"])
            v = leggi_numero(v_raw, tabella["separatore"])
            if t is INVALIDO or t is None or v is INVALIDO or v is None:
                raise ValueError(
                    f"Riga {numero_riga}, coppia {nome_t}:{nome_v}: "
                    "timestamp e valori devono essere numerici e finiti."
                )
            if tempi and float(t) <= tempi[-1]:
                raise ValueError(
                    f"Riga {numero_riga}: timestamp non strettamente crescenti "
                    "nell'ordine delle coppie confermato."
                )
            tempi.append(float(t))
            valori.append(float(v))
        if esclusa:
            serie.append(None)
        elif not tempi:
            raise ValueError(
                f"Riga {numero_riga}: la serie è completamente vuota. "
                "Nessuna dissimilarità viene inventata: correggi il CSV "
                "oppure escludi il percorso della riga."
            )
        else:
            serie.append({"tempi": tempi, "valori": valori})
    return serie


def _verifica_serie_a_coppie_percorso(
    percorso: dict[str, Any], risultato: dict[str, Any],
) -> None:
    if percorso.get("tipoGruppo") != "tempo_coppie" or percorso["stato"] == "da_completare":
        return
    try:
        serie = _serie_da_coppie(risultato["originale"], percorso)
        valide = [s for s in serie if s is not None]
        if len(valide) < 2:
            raise ValueError("Restano meno di due serie non vuote confrontabili.")
        params = percorso["parametri"]
        if percorso["metodo"] == "Dynamic Time Warping" and "finestra" in params:
            lunghezze = [len(s["valori"]) for s in valide]
            if max(lunghezze) - min(lunghezze) > params["finestra"]:
                raise ValueError(
                    "La finestra DTW dichiarata rende impossibile il cammino "
                    "tra almeno due serie di lunghezza diversa."
                )
        percorso["righeSerieValide"] = len(valide)
        percorso["lunghezzeSerie"] = [
            len(s["valori"]) if s is not None else None for s in serie
        ]
    except ValueError as errore:
        percorso["stato"] = "da_completare"
        percorso["calcolo"]["disponibile"] = False
        percorso["calcolo"]["descrizione"] = "Controlla le coppie temporali."
        percorso.setdefault("avvisi", []).append(str(errore))


def _leggi_griglia_temporale(testo: str, numero: int) -> list[float]:
    """Coordinate fisiche della stessa griglia per tutte le osservazioni."""
    parti = [s.strip() for s in testo.split(";")]
    if len(parti) != numero or any(not s for s in parti):
        raise ValueError(
            f"I timestamp devono essere esattamente {numero} numeri, "
            "separati da punto e virgola, uno per ogni colonna nell'ordine confermato."
        )
    try:
        tempi = [float(s.replace(",", ".")) for s in parti]
    except ValueError as errore:
        raise ValueError("I timestamp devono essere numeri finiti.") from errore
    if any(not math.isfinite(t) for t in tempi):
        raise ValueError("I timestamp devono essere numeri finiti.")
    if any(b <= a for a, b in zip(tempi, tempi[1:])):
        raise ValueError("I timestamp devono essere strettamente crescenti.")
    return tempi


def _passi_temporali_regolari(tempi: list[float]) -> bool:
    intervalli = [b - a for a, b in zip(tempi, tempi[1:])]
    return all(math.isclose(d, intervalli[0], rel_tol=1e-9,
                            abs_tol=1e-10 * abs(intervalli[0]))
               for d in intervalli[1:])


def _distanza_pendenze(
    x: list[float], y: list[float], tempi: list[float],
) -> float:
    if len(x) != len(y) or len(x) != len(tempi) or len(x) < 2:
        raise ValueError("Le pendenze richiedono almeno due valori sulla stessa griglia.")
    if any(not math.isfinite(v) for v in [*x, *y, *tempi]):
        raise ValueError("Le serie e i tempi devono essere finiti.")
    if any(b <= a for a, b in zip(tempi, tempi[1:])):
        raise ValueError("La griglia temporale non è strettamente crescente.")
    return math.sqrt(math.fsum(
        (((x[i+1] - x[i]) - (y[i+1] - y[i])) / (tempi[i+1] - tempi[i])) ** 2
        for i in range(len(x) - 1)
    ))


def _distanza_lcss(
    x: list[float], y: list[float], tempi_x: list[float], tempi_y: list[float],
    tolleranza_valori: float, tolleranza_tempo: float,
) -> float:
    n, m = len(x), len(y)
    if not n or not m or len(tempi_x) != n or len(tempi_y) != m:
        raise ValueError("LCSS richiede serie non vuote con timestamp corrispondenti.")
    if n * m > 2_000_000:
        raise ValueError("Le sequenze sono troppo lunghe per LCSS esatta nel browser.")
    if not all(math.isfinite(v) for v in [*x, *y, *tempi_x, *tempi_y]):
        raise ValueError("LCSS richiede valori e istanti finiti.")
    if not all(math.isfinite(v) and v >= 0 for v in (tolleranza_valori, tolleranza_tempo)):
        raise ValueError("Le tolleranze LCSS devono essere finite e non negative.")
    prev = [0] * (m + 1)
    for i in range(1, n + 1):
        curr = [0] * (m + 1)
        for j in range(1, m + 1):
            if (abs(x[i-1] - y[j-1]) <= tolleranza_valori
                    and abs(tempi_x[i-1] - tempi_y[j-1]) <= tolleranza_tempo):
                curr[j] = prev[j-1] + 1
            else:
                curr[j] = max(prev[j], curr[j-1])
        prev = curr
    return 1 - prev[m] / min(n, m)


def _interpola_vuoti_temporali(
    valori: list[float | None], tempi: list[float],
) -> list[float] | None:
    """Solo vuoti interni: interpolazione lineare sui timestamp effettivi."""
    if len(valori) != len(tempi) or not valori or valori[0] is None or valori[-1] is None:
        return None
    risultato = list(valori)
    i = 1
    while i < len(risultato) - 1:
        if risultato[i] is not None:
            i += 1
            continue
        sx = i - 1
        dx = i
        while dx < len(risultato) and risultato[dx] is None:
            dx += 1
        if dx == len(risultato):
            return None
        if tempi[dx] <= tempi[sx]:
            raise ValueError("I timestamp non sono strettamente crescenti.")
        for j in range(i, dx):
            quota = (tempi[j] - tempi[sx]) / (tempi[dx] - tempi[sx])
            risultato[j] = (1 - quota) * float(risultato[sx]) + quota * float(risultato[dx])
        i = dx + 1
    return [float(x) for x in risultato]


def _distanza_dtw(
    x: list[float], y: list[float],
    parametri: dict[str, Any] | None = None,
) -> float:
    """Minimo ESATTO del costo medio per passo, non costo totale diviso per la lunghezza.

    Per ogni cella e lunghezza di cammino conserva il costo totale minimo.
    La minimizzazione finale viene fatta sui rapporti costo/lunghezza.
    """
    if not x or not y:
        raise ValueError("La DTW richiede due serie temporali non vuote.")
    if any(not math.isfinite(v) for v in [*x, *y]):
        raise ValueError("La DTW richiede valori numerici finiti.")
    parametri = parametri or {}
    n, m = len(x), len(y)
    costo_tipo = parametri.get("costoLocale", "assoluto")
    if costo_tipo not in {"assoluto", "quadratico"}:
        raise ValueError("Costo locale DTW non riconosciuto.")
    finestra = parametri.get("finestra")
    if finestra is not None and (
        type(finestra) is not int or finestra < abs(n - m)
    ):
        raise ValueError(
            "La finestra DTW deve essere un intero non negativo e consentire "
            "un cammino fra le due estremità."
        )
    peso_ritardo = parametri.get("lambdaRitardo")
    tau = parametri.get("tauRitardo")
    tempi = parametri.get("tempi", [])
    tempi_x = parametri.get("tempiX", tempi)
    tempi_y = parametri.get("tempiY", tempi)
    if peso_ritardo is not None:
        if (not math.isfinite(peso_ritardo) or peso_ritardo < 0
                or not isinstance(tau, (int, float))
                or not math.isfinite(tau) or tau <= 0
                or len(tempi_x) != n or len(tempi_y) != m
                or any(not math.isfinite(t) for t in [*tempi_x, *tempi_y])):
            raise ValueError("La penalità DTW richiede λ≥0, τ>0 e timestamp completi.")
    if n * m * (n + m) > 4_000_000:
        raise ValueError(
            "Le serie sono troppo lunghe per la DTW esatta a costo medio nel browser. "
            "Riduci la risoluzione con un ricampionamento esplicito."
        )
    # Ogni cammino ammissibile parte da (0,0), termina in (n-1,m-1)
    # e usa esclusivamente i passi (1,0), (0,1), (1,1).
    tabella: list[list[dict[int, float]]] = [
        [dict() for _ in range(m)] for _ in range(n)
    ]
    for i in range(n):
        for j in range(m):
            if finestra is not None and abs(i - j) > finestra:
                continue
            scarto = abs(x[i] - y[j])
            costo_locale = scarto if costo_tipo == "assoluto" else scarto ** 2
            if peso_ritardo is not None:
                costo_locale += peso_ritardo * abs(tempi_x[i] - tempi_y[j]) / tau
            if i == 0 and j == 0:
                tabella[i][j][1] = costo_locale
                continue
            corrente = tabella[i][j]
            for ii, jj in ((i - 1, j), (i, j - 1), (i - 1, j - 1)):
                if ii < 0 or jj < 0:
                    continue
                for lunghezza, costo_precedente in tabella[ii][jj].items():
                    nuova_lunghezza = lunghezza + 1
                    nuovo_costo = costo_precedente + costo_locale
                    if nuovo_costo < corrente.get(nuova_lunghezza, math.inf):
                        corrente[nuova_lunghezza] = nuovo_costo
    cammini = tabella[-1][-1]
    if not cammini:
        raise ValueError("Non esistono cammini di allineamento DTW ammissibili.")
    return min(costo / lunghezza for lunghezza, costo in cammini.items())


def _interpola_vuoti_interni(valori: list[float | None]) -> list[float] | None:
    if not valori or valori[0] is None or valori[-1] is None:
        return None
    risultato = list(valori)
    indice = 1
    while indice < len(risultato) - 1:
        if risultato[indice] is not None:
            indice += 1
            continue
        inizio = indice - 1
        fine = indice
        while fine < len(risultato) and risultato[fine] is None:
            fine += 1
        if fine == len(risultato):
            return None
        sinistra = float(risultato[inizio])
        destra = float(risultato[fine])
        ampiezza = fine - inizio
        for posizione in range(indice, fine):
            quota = (posizione - inizio) / ampiezza
            risultato[posizione] = sinistra + quota * (destra - sinistra)
        indice = fine + 1
    return [float(valore) for valore in risultato]


def _normalizza_masse_distribuzione(
    valori: list[float], natura: str
) -> list[float]:
    if not valori or any(not math.isfinite(v) or v < 0 for v in valori):
        raise ValueError("Una distribuzione richiede masse finite e non negative.")
    totale = math.fsum(valori)
    if not math.isfinite(totale) or totale <= 0:
        raise ValueError("La massa totale deve essere strettamente positiva.")
    if natura == "probabilita":
        if not math.isclose(totale, 1.0, rel_tol=1e-6, abs_tol=1e-9):
            raise ValueError(
                "Le probabilità devono avere somma 1. "
                "Dichiara masse se desideri la normalizzazione per riga."
            )
    elif natura != "masse":
        raise ValueError("Conferma se si tratta di probabilità oppure di masse.")
    # Anche nel caso probabilità eliminiamo il solo errore di arrotondamento.
    return [valore / totale for valore in valori]


def _distanza_distribuzioni(
    x: list[float], y: list[float],
    id_misura: str, natura: str,
) -> float:
    """Hellinger e radice della divergenza Jensen–Shannon / ln(2).

    Entrambe sono distanze in [0,1] sul simplesso di probabilità.
    I termini 0 log(0/m) sono 0 per continuità, senza pseudoconteggi.
    """
    if len(x) != len(y) or not x:
        raise ValueError("Le distribuzioni devono avere gli stessi bin.")
    p = _normalizza_masse_distribuzione(x, natura)
    q = _normalizza_masse_distribuzione(y, natura)
    if id_misura == "hellinger":
        quadrato = math.fsum(
            (math.sqrt(a) - math.sqrt(b)) ** 2 for a, b in zip(p, q)
        ) / 2.0
        return math.sqrt(max(0.0, min(1.0, quadrato)))
    if id_misura == "jensen_shannon":
        divergenza = 0.0
        for a, b in zip(p, q):
            media = (a + b) / 2.0
            if a > 0:
                divergenza += a * math.log(a / media) / 2.0
            if b > 0:
                divergenza += b * math.log(b / media) / 2.0
        return math.sqrt(max(0.0, min(1.0, divergenza / math.log(2.0))))
    raise ValueError("Misura di confronto fra distribuzioni non riconosciuta.")


def _distanza_specializzata(
    x: list[float], y: list[float], metodo: str,
    id_misura: str | None = None, parametri: dict[str, Any] | None = None,
) -> float | None:
    if id_misura in {"euclidean", "manhattan", "chebyshev", "minkowski", "weighted_minkowski"}:
        return _distanza_numerica(x, y, id_misura, parametri or {})
    if id_misura in {"hellinger", "jensen_shannon"}:
        return _distanza_distribuzioni(
            x, y, id_misura, (parametri or {}).get("natura", "")
        )
    if metodo in {"Distanza tra coordinate", "Distanza punto per punto"}:
        return math.sqrt(sum((a - b) ** 2 for a, b in zip(x, y)))
    if metodo == "Dissimilarità coseno":
        norma_x = math.sqrt(sum(valore**2 for valore in x))
        norma_y = math.sqrt(sum(valore**2 for valore in y))
        if norma_x == 0 or norma_y == 0:
            return None
        coseno = sum(a * b for a, b in zip(x, y)) / (norma_x * norma_y)
        return 1.0 - max(-1.0, min(1.0, coseno))
    if metodo == "Dissimilarità di Pearson":
        correlazione = _correlazione_pearson(x, y)
        return None if correlazione is None else 1.0 - correlazione
    if metodo == "Dissimilarità di Spearman":
        correlazione = _correlazione_pearson(_ranghi_medi(x), _ranghi_medi(y))
        return None if correlazione is None else 1.0 - correlazione
    if metodo == "Dissimilarità di Kendall τ-b":
        correlazione = _kendall_tau_b(x, y)
        return None if correlazione is None else (1.0 - correlazione) / 2.0
    if metodo == "Dynamic Time Warping":
        return _distanza_dtw(x, y, parametri)
    if metodo == "Distanza sulle pendenze":
        return _distanza_pendenze(x, y, (parametri or {}).get("tempi", []))
    if metodo == "Dissimilarità LCSS normalizzata":
        params = parametri or {}
        tempi = params.get("tempi", [])
        return _distanza_lcss(
            x, y, tempi, tempi, params["tolleranzaValori"], params["tolleranzaTempo"]
        )
    if metodo == "Distanza composizionale di Aitchison":
        if any(valore <= 0 for valore in [*x, *y]):
            raise ValueError("La distanza di Aitchison richiede componenti strettamente positive.")
        log_x = [math.log(valore) for valore in x]
        log_y = [math.log(valore) for valore in y]
        media_x = sum(log_x) / len(log_x)
        media_y = sum(log_y) / len(log_y)
        return math.sqrt(sum(
            ((a - media_x) - (b - media_y)) ** 2
            for a, b in zip(log_x, log_y)
        ))
    raise ValueError(f"Misura specializzata non riconosciuta: {metodo}.")


def _calcola_matrice_specializzata(
    risultato: dict[str, Any],
    interpretazione: dict[str, Any],
    percorso: dict[str, Any],
) -> dict[str, Any]:
    tabella = risultato["originale"]
    nomi = percorso["colonne"]
    indici = [tabella["intestazioni"].index(nome) for nome in nomi]
    metodo = percorso["metodo"]
    n = len(tabella["righe"])
    matrice: list[list[float | None]] = [[0.0 for _ in range(n)] for _ in range(n)]
    epsilon_aitchison: float | None = None

    if percorso["tipo"] == "separato":
        strategia = percorso["mancanti"].get("strategia")
        valori = [
            None if mancante(riga[indici[0]]) and strategia == "escludi_percorso"
            else "" if mancante(riga[indici[0]]) and strategia in {"stringa_vuota", "insieme_vuoto"}
            else riga[indici[0]]
            for riga in tabella["righe"]
        ]
        for i in range(n):
            for k in range(i + 1, n):
                if valori[i] is None or valori[k] is None:
                    distanza = None
                elif metodo == "Uguale o diverso":
                    distanza = 0.0 if str(valori[i]).strip() == str(valori[k]).strip() else 1.0
                elif metodo == "Distanza di Levenshtein normalizzata":
                    distanza = _levenshtein_normalizzata(
                        str(valori[i]).strip(), str(valori[k]).strip()
                    )
                elif metodo == "Distanza di Hamming normalizzata":
                    distanza = _hamming_normalizzata(
                        str(valori[i]).strip(), str(valori[k]).strip()
                    )
                elif metodo == "Distanza di Damerau–Levenshtein normalizzata":
                    distanza = _damerau_levenshtein_normalizzata(
                        str(valori[i]).strip(), str(valori[k]).strip()
                    )
                elif metodo in {"Dissimilarità di Jaccard tra insiemi", "Dissimilarità di Dice tra insiemi"}:
                    specifica = percorso["parametri"]
                    insieme_i = _leggi_insieme_etichette(str(valori[i]), specifica, strategia)
                    insieme_k = _leggi_insieme_etichette(str(valori[k]), specifica, strategia)
                    distanza = _distanza_insiemi(
                        insieme_i, insieme_k, specifica["misura"]
                    )
                elif metodo == "Distanza ciclica normalizzata":
                    periodo = float(str(percorso["parametri"]["periodo"]).replace(",", "."))
                    valore_i = leggi_numero(valori[i], tabella["separatore"])
                    valore_k = leggi_numero(valori[k], tabella["separatore"])
                    if valore_i is INVALIDO or valore_k is INVALIDO or valore_i is None or valore_k is None:
                        raise ValueError("La grandezza ciclica richiede valori numerici completi.")
                    distanza = _distanza_ciclica(float(valore_i), float(valore_k), periodo)
                else:
                    raise ValueError(f"Il confronto separato “{metodo}” non è ancora calcolabile.")
                matrice[i][k] = distanza
                matrice[k][i] = distanza
        limite: float | None = 1.0
    elif percorso.get("tipoGruppo") == "tempo_coppie":
        serie = _serie_da_coppie(tabella, percorso)
        params = percorso.get("parametri", {})
        for i in range(n):
            for k in range(i + 1, n):
                if serie[i] is None or serie[k] is None:
                    distanza = None
                elif metodo == "Dynamic Time Warping":
                    config = {
                        chiave: params[chiave] for chiave in
                        ("costoLocale", "finestra", "lambdaRitardo", "tauRitardo")
                        if chiave in params
                    }
                    config["tempiX"] = serie[i]["tempi"]
                    config["tempiY"] = serie[k]["tempi"]
                    distanza = _distanza_dtw(
                        serie[i]["valori"], serie[k]["valori"], config
                    )
                elif metodo == "Dissimilarità LCSS normalizzata":
                    distanza = _distanza_lcss(
                        serie[i]["valori"], serie[k]["valori"],
                        serie[i]["tempi"], serie[k]["tempi"],
                        params["tolleranzaValori"], params["tolleranzaTempo"]
                    )
                else:
                    raise ValueError("Scegli DTW o LCSS per le serie a tempi individuali.")
                matrice[i][k] = matrice[k][i] = distanza
        limite = 1.0 if metodo == "Dissimilarità LCSS normalizzata" else None
    elif percorso.get("tipoGruppo") == "vettore_binario":
        vettori_binari = _decodifica_vettori_binari(risultato, percorso)
        for i in range(n):
            for k in range(i + 1, n):
                distanza = (
                    None if vettori_binari[i] is None or vettori_binari[k] is None
                    else _distanza_vettori_binari(
                        vettori_binari[i], vettori_binari[k], percorso["idMisura"],
                        consenti_indefiniti=(
                            percorso["mancanti"]["strategia"] == "pairwise"
                        ),
                    )
                )
                matrice[i][k] = matrice[k][i] = distanza
        limite = 1.0
    else:
        analisi_per_nome = {colonna["nome"]: colonna for colonna in risultato["colonne"]}
        strategia = percorso["mancanti"].get("strategia")
        vettori_grezzi: list[list[float | None]] = []
        for riga in tabella["righe"]:
            vettore: list[float | None] = []
            for nome, indice in zip(nomi, indici):
                valore = leggi_numero(riga[indice], tabella["separatore"])
                if valore is INVALIDO:
                    raise ValueError(f"La colonna “{nome}” contiene valori non numerici.")
                vettore.append(None if valore is None else float(valore))
            vettori_grezzi.append(vettore)

        vettori: list[list[float] | None] = []
        for vettore in vettori_grezzi:
            if all(valore is not None for valore in vettore):
                vettori.append([float(valore) for valore in vettore])
            elif strategia == "escludi_percorso":
                vettori.append(None)
            elif strategia == "pairwise":
                vettori.append(list(vettore))
            elif strategia == "interpola_lineare":
                if percorso.get("tipoGruppo") == "tempo":
                    vettori.append(_interpola_vuoti_temporali(
                        vettore, percorso.get("parametri", {}).get("tempi", [])
                    ))
                else:
                    vettori.append(_interpola_vuoti_interni(vettore))
            elif strategia in {"imputa_mediana", "imputa_media", "zero"}:
                completato: list[float] = []
                for nome, valore in zip(nomi, vettore):
                    if valore is not None:
                        completato.append(float(valore))
                    elif strategia == "zero":
                        completato.append(0.0)
                    else:
                        chiave = "mediana" if strategia == "imputa_mediana" else "media"
                        sostituto = analisi_per_nome[nome].get("statistiche", {}).get(chiave)
                        if sostituto is None:
                            raise ValueError(
                                f"Non è possibile stimare {chiave} per la colonna “{nome}”."
                            )
                        completato.append(float(sostituto))
                vettori.append(completato)
            else:
                raise ValueError(
                    f"Definisci come trattare i mancanti nel gruppo “{percorso['titolo']}”."
                )

        if percorso["preelaborazione"]["usaTabellaTrasformata"]:
            metodi = {
                passo["colonna"]: passo["metodo"]
                for passo in percorso["preelaborazione"]["passi"]
            }
            vettori = [
                None if vettore is None else [
                    _trasforma_per_percorso(valore, analisi_per_nome[nome], metodi.get(nome, "nessuno"))
                    for nome, valore in zip(nomi, vettore)
                ]
                for vettore in vettori
            ]

        if metodo == "Distanza composizionale di Aitchison" and any(
            vettore is not None and any(valore == 0 for valore in vettore)
            for vettore in vettori
        ):
            if interpretazione.get(f"zeri-aitchison-{percorso.get('idGruppo')}") != "sostituisci":
                raise ValueError("Specifica come trattare gli zeri prima di usare Aitchison.")
            chiusi: list[list[float] | None] = []
            for vettore in vettori:
                if vettore is None:
                    chiusi.append(None)
                    continue
                if any(valore < 0 for valore in vettore):
                    raise ValueError("Aitchison non è definita per componenti negative.")
                totale = sum(vettore)
                if totale <= 0:
                    raise ValueError("Aitchison richiede una somma positiva in ogni riga.")
                chiusi.append([valore / totale for valore in vettore])
            positivi = [
                valore for vettore in chiusi if vettore is not None
                for valore in vettore if valore > 0
            ]
            if not positivi:
                raise ValueError("Aitchison richiede almeno un valore positivo osservato.")
            massimo_zeri = max(
                sum(valore == 0 for valore in vettore)
                for vettore in chiusi if vettore is not None
            )
            epsilon_aitchison = min(min(positivi) / 2, 1 / (2 * massimo_zeri))
            vettori = [
                None if vettore is None else (
                    vettore if not any(valore == 0 for valore in vettore) else [
                        epsilon_aitchison if valore == 0
                        else valore * (
                            (1 - sum(elemento == 0 for elemento in vettore) * epsilon_aitchison)
                            / sum(elemento for elemento in vettore if elemento > 0)
                        )
                        for valore in vettore
                    ]
                )
                for vettore in chiusi
            ]
        for i in range(n):
            for k in range(i + 1, n):
                distanza = (
                    None if vettori[i] is None or vettori[k] is None
                    else _distanza_coordinate_comuni(
                        vettori[i], vettori[k],
                        percorso["idMisura"], percorso.get("parametri", {})
                    ) if strategia == "pairwise"
                    else None if vettori[i] is None or vettori[k] is None
                    else _distanza_specializzata(
                        vettori[i], vettori[k], metodo,
                        percorso.get("idMisura"), percorso.get("parametri"),
                    )
                )
                matrice[i][k] = distanza
                matrice[k][i] = distanza
        limite = (
            2.0 if metodo in {
                "Dissimilarità coseno", "Dissimilarità di Pearson", "Dissimilarità di Spearman"
            } else 1.0 if metodo in {
                "Dissimilarità di Kendall τ-b", "Distanza di Hellinger",
                "Distanza di Jensen–Shannon",
                "Dissimilarità LCSS normalizzata"
            } else None
        )

    etichette = _etichette_righe(risultato, interpretazione)
    righe_csv = [[etichetta, *riga] for etichetta, riga in zip(etichette, matrice)]
    nota = (
        f"Calcolata sul percorso “{percorso['titolo']}” usando "
        + ("le trasformazioni numeriche confermate." if percorso["preelaborazione"]["usaTabellaTrasformata"]
           else "i valori originali.")
    )
    if metodo in {"Dissimilarità di Jaccard tra insiemi", "Dissimilarità di Dice tra insiemi"}:
        nota += (
            " Ogni cella viene interpretata come insieme di etichette; "
            "[] è un insieme vuoto osservato, distinto dai mancanti. "
            "Etichette ripetute contano una sola volta. "
            "Confronto di due insiemi vuoti: dissimilarità zero."
        )
    if metodo == "Distanza ciclica normalizzata":
        nota += (
            f" Periodo P={percorso['parametri']['periodo']} "
            f"({percorso['parametri']['unita']}); "
            "valori richiesti in [0,P), senza correzioni modulari implicite."
        )
    if percorso.get("tipoGruppo") == "tempo_coppie":
        params = percorso.get("parametri", {})
        nota += (
            " I timestamp sono letti da coppie di colonne esplicite, "
            "diverse per ciascuna riga e strettamente crescenti. "
            f"Unità: {params.get('unitaTempo')}. "
            "Nessun ricampionamento o imputazione implicita."
        )
        if metodo == "Dynamic Time Warping":
            nota += (
                " DTW a minimo costo medio esatto, costo locale "
                f"{params.get('costoLocale')}; finestra={params.get('finestra', 'nessuna')}; "
                f"λ={params.get('lambdaRitardo', 'non applicato')}; "
                f"τ={params.get('tauRitardo', 'non applicato')}."
            )
            if params.get("timestampIgnoratiNelCosto"):
                nota += " Lo sfasamento temporale è ignorato per scelta esplicita."
        else:
            nota += (
                " LCSS con tolleranze su valore e tempo "
                f"({params.get('tolleranzaValori')}, {params.get('tolleranzaTempo')}); "
                "normalizzazione 1−LCSS/min(lunghezze)."
            )
    if percorso.get("tipoGruppo") == "vettore_binario":
        nota += (
            " Il gruppo confronta simultaneamente tutte le colonne come "
            "un vettore binario (0/1); nessuna caratteristica è conteggiata "
            "separatamente in Gower."
        )
        if percorso["mancanti"]["strategia"] == "pairwise":
            nota += (
                " Le distanze sono calcolate solo sulle coordinate osservate "
                "congiuntamente. Se non ve ne sono, il contributo locale "
                "è non disponibile (non zero); Jaccard sui soli doppi zeri "
                "osservati vale zero, mentre Dice è non definita."
            )
        if percorso.get("idMisura") == "dice":
            nota += (
                " Dice ignora le co-assenze; nessun vettore nullo è ammesso. "
                "La dissimilarità può non rispettare la disuguaglianza triangolare."
            )
    if percorso.get("tipoGruppo") == "distribuzione":
        natura = percorso.get("parametri", {}).get("natura")
        nota += (
            " Probabilità già normalizzate: ogni somma di riga verificata pari a 1 "
            "(salvo tolleranza numerica); nessun pseudoconteggio applicato."
            if natura == "probabilita" else
            " Frequenze o masse non negative normalizzate alla somma di ogni "
            "riga; nessun pseudoconteggio applicato."
        )
    if percorso.get("tipoGruppo") == "tempo":
        params = percorso.get("parametri", {})
        nota += (
            " Ordine temporale confermato: "
            + " → ".join(percorso["colonne"])
            + f". Campionamento {params.get('campionamento')} "
            + f"su griglia comune ({params.get('unitaTempo', 'non specificata')}): "
            + "; ".join(format(t, ".9g") for t in params.get("tempi", []))
            + ". Nessun ricampionamento implicito."
        )
        if metodo == "Dynamic Time Warping":
            nota += (
                " DTW: minimo esatto del rapporto costo/lunghezza, "
                f"costo locale {params.get('costoLocale', 'assoluto')}; "
                f"finestra {params.get('finestra', 'nessuna')}, "
                f"penalità temporale λ={params.get('lambdaRitardo', 'assente')} "
                f"e τ={params.get('tauRitardo', 'assente')}."
            )
        elif metodo == "Dissimilarità LCSS normalizzata":
            nota += (
                f" LCSS: tolleranza valori={params.get('tolleranzaValori')}, "
                f"tolleranza temporale={params.get('tolleranzaTempo')}; "
                "dissimilarità 1 - LCSS/min(m,n)."
            )
        elif metodo == "Distanza sulle pendenze":
            nota += (
                " La distanza sulle pendenze annulla traslazioni verticali "
                "costanti ed è una pseudometrica sullo spazio dei profili."
            )
    if percorso["mancanti"]["presenza"]:
        nota += " " + percorso["mancanti"]["descrizione"]
    if percorso["tipo"] == "gruppo" and metodo == "Distanza composizionale di Aitchison":
        if epsilon_aitchison is not None:
            nota += (
                " Dopo la chiusura a somma 1, gli zeri sono stati sostituiti con "
                f"{format(epsilon_aitchison, '.6g')} e le componenti positive sono "
                "state ridimensionate proporzionalmente."
            )
    return {
        "metodo": metodo,
        "colonne": nomi,
        "etichette": etichette,
        "matrice": matrice,
        "indiciRighe": list(range(n)),
        "limiteAggregazione": limite,
        "csv": crea_csv(["Riga", *etichette], righe_csv),
        "nota": nota,
    }


def _normalizza_per_aggregazione_con_diagnostica(
    risultato_percorso: dict[str, Any],
    specifica: dict[str, Any] | None = None,
) -> tuple[list[list[float | None]], str, dict[str, Any]]:
    """Normalizza conservando le coppie non disponibili, senza dati inventati.

    Se la misura ha massimo teorico, questo prevale. Se non lo ha, il
    massimo campionario usa solo coppie distinte definite. La variante
    robusta e' ammessa soltanto su richiesta dell'utente.
    """
    matrice = risultato_percorso["matrice"]
    n = len(matrice)
    if any(len(riga) != n for riga in matrice):
        raise ValueError("La matrice locale non e' quadrata.")
    indici = risultato_percorso.get("indiciRighe", list(range(n)))
    if len(indici) != n or len(set(indici)) != n:
        raise ValueError("Gli indici delle righe della matrice locale non sono coerenti.")
    limite = risultato_percorso.get("limiteAggregazione")
    metodo = (
        specifica.get("metodo", "")
        if specifica is not None
        else "teorica" if limite is not None else "campionaria"
    )
    valori_validi: list[tuple[int, int, float]] = []
    for i in range(n):
        for j in range(i + 1, n):
            x, y = matrice[i][j], matrice[j][i]
            if x is None or y is None:
                if x is not None or y is not None:
                    raise ValueError("La disponibilita' della dissimilarita' locale non e' simmetrica.")
                continue
            x, y = float(x), float(y)
            if not math.isfinite(x) or not math.isfinite(y) or x < 0 or y < 0:
                raise ValueError("La matrice locale contiene dissimilarita' negative o non finite.")
            if abs(x-y) > 1e-10:
                raise ValueError("La dissimilarita' locale non e' simmetrica.")
            valori_validi.append((i, j, x))
    if not valori_validi:
        raise ValueError(
            "Questo percorso non contiene coppie distinte confrontabili: "
            "rivedi i mancanti, le colonne o la misura prima di aggregarlo."
        )

    massimo = max(v for _, _, v in valori_validi)
    if metodo == "teorica":
        if limite is None:
            raise ValueError("Questo percorso non dispone di un massimo teorico utilizzabile.")
        scala = float(limite)
        if not math.isfinite(scala) or scala <= 0:
            raise ValueError("Il massimo teorico deve essere finito e positivo.")
        if massimo > scala + 1e-9 * max(1.0, scala):
            raise ValueError("La dissimilarita' supera il massimo teorico dichiarato.")
        descrizione = f"scala teorica 0–{format(scala, '.12g')}"
    elif metodo == "campionaria":
        if limite is not None:
            raise ValueError("Per questa misura si deve conservare la scala teorica.")
        scala = massimo if massimo > 0 else 1.0
        descrizione = (
            f"massimo campionario = {format(scala, '.6g')}"
            if massimo > 0 else "tutte le dissimilarita' definite sono nulle"
        )
    elif metodo == "robusta":
        if limite is not None:
            raise ValueError("La scala robusta non e' applicabile a questa misura gia' limitata.")
        righe_anomale = (specifica or {}).get("righeAnomale", [])
        if (
            not isinstance(righe_anomale, list)
            or not righe_anomale
            or any(not isinstance(v, int) or v < 1 for v in righe_anomale)
            or len(righe_anomale) != len(set(righe_anomale))
        ):
            raise ValueError("Conferma almeno una riga anomala valida per la scala robusta.")
        escluse = set(righe_anomale)
        non_anomale = {k for k, indice in enumerate(indici) if indice + 1 not in escluse}
        if len(non_anomale) < 2:
            raise ValueError("La scala robusta richiede almeno due righe non anomale.")
        confronti_non_anomali = [
            v for i, j, v in valori_validi if i in non_anomale and j in non_anomale
        ]
        if not confronti_non_anomali:
            raise ValueError(
                "Non esistono due righe non anomale confrontabili per stimare la scala robusta."
            )
        scala_robusta = max(confronti_non_anomali)
        if scala_robusta == 0 and massimo > 0:
            raise ValueError(
                "La scala robusta e' zero, ma esistono dissimilarita' positive. "
                "Rivedi le righe anomale o seleziona il massimo campionario."
            )
        scala = scala_robusta if scala_robusta > 0 else 1.0
        descrizione = (
            f"massimo robusto = {format(scala_robusta, '.6g')}, "
            f"righe escluse soltanto dalla scala: {', '.join(map(str, sorted(escluse)))}"
            if massimo > 0 else
            "tutte le dissimilarita' definite sono nulle, scala robusta confermata"
        )
    else:
        raise ValueError("Metodo di normalizzazione locale non riconosciuto.")

    normalizzata = [
        [
            None if valore is None else
            min(max(float(valore) / scala, 0.0), 1.0)
            for valore in riga
        ]
        for riga in matrice
    ]
    sature = sum(v > scala for _, _, v in valori_validi)
    diagnostica = {
        "metodo": metodo,
        "scala": scala,
        "coppieValide": len(valori_validi),
        "coppieSaturate": sature if metodo == "robusta" else 0,
        "righeEscluseSoloDallaScala": (specifica or {}).get("righeAnomale", [])
            if metodo == "robusta" else [],
    }
    if metodo == "robusta":
        descrizione += f"; coppie saturate a 1: {sature}"
    return normalizzata, descrizione, diagnostica


def _normalizza_per_aggregazione(
    risultato_percorso: dict[str, Any],
    specifica: dict[str, Any] | None = None,
) -> tuple[list[list[float | None]], str]:
    """Compatibilita' con gli utilizzi esistenti: matrice, descrizione."""
    matrice, descrizione, _ = _normalizza_per_aggregazione_con_diagnostica(
        risultato_percorso, specifica
    )
    return matrice, descrizione


def _diagnostica_distribuzione_finale(coppie: list[float]) -> dict[str, Any]:
    """Descrizione delle sole coppie i<j, senza alterare la matrice.

    Quantili empirici con interpolazione lineare: posizione p*(m-1).
    I cinque intervalli sono [0, .2), ..., [.8, 1]; l'ultimo include 1.
    Le quote descrivono il campione, non sono probabilita' inferenziali.
    """
    ordinati = sorted(coppie)
    m = len(ordinati)

    def quantile(p: float) -> float | None:
        if not m:
            return None
        posizione = p * (m - 1)
        inferiore = math.floor(posizione)
        superiore = math.ceil(posizione)
        quota = posizione - inferiore
        return ordinati[inferiore] * (1 - quota) + ordinati[superiore] * quota

    conteggi = [0, 0, 0, 0, 0]
    for valore in coppie:
        if not math.isfinite(valore) or not 0 <= valore <= 1:
            raise ValueError("La distribuzione richiede dissimilarita' finite in [0,1].")
        indice = min(4, int(valore * 5))
        conteggi[indice] += 1

    return {
        "numeroCoppie": m,
        "minimo": ordinati[0] if m else None,
        "massimo": ordinati[-1] if m else None,
        "media": math.fsum(ordinati) / m if m else None,
        "mediana": quantile(.5),
        "primoQuartile": quantile(.25),
        "terzoQuartile": quantile(.75),
        "coppieZero": sum(x <= 1e-12 for x in ordinati),
        "coppieUno": sum(x >= 1 - 1e-12 for x in ordinati),
        "intervalli": [
            {
                "inizio": k / 5,
                "fine": (k + 1) / 5,
                "fineInclusa": k == 4,
                "coppie": conteggi[k],
                "frazione": conteggi[k] / m if m else 0.0,
            }
            for k in range(5)
        ],
    }


def _valida_matrice_finale(
    matrice: list[list[float | None]], etichette: list[str],
) -> dict[str, Any]:
    """Decisioni 9 e 45: validazione obbligatoria e avvisi non bloccanti."""
    n = len(etichette)
    if len(matrice) != n or any(len(riga) != n for riga in matrice):
        raise ValueError("La matrice finale non e' quadrata o non corrisponde alle righe.")

    non_disponibili: list[tuple[int, int]] = []
    for i in range(n):
        for j in range(i, n):
            x = matrice[i][j]
            y = matrice[j][i]
            if x is None or y is None:
                if x is not None or y is not None:
                    raise ValueError(
                        f"La disponibilita' della matrice finale non e' simmetrica: "
                        f"({i + 1}, {j + 1})."
                    )
                if i != j:
                    non_disponibili.append((i, j))
                else:
                    raise ValueError("La diagonale della matrice finale non e' definita.")
                continue
            if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
                raise ValueError(f"Valore non numerico nella matrice finale: ({i + 1}, {j + 1}).")
            if not math.isfinite(x) or not math.isfinite(y):
                raise ValueError(f"Valore non finito nella matrice finale: ({i + 1}, {j + 1}).")
            if abs(float(x) - float(y)) > 1e-10:
                raise ValueError(f"La matrice finale non e' simmetrica: ({i + 1}, {j + 1}).")
            if i == j and abs(float(x)) > 1e-12:
                raise ValueError(f"La diagonale della matrice finale deve essere nulla (riga {i + 1}).")
            # Verificare ENTRAMBI i triangoli: la vicinanza fra x e y
            # non autorizza un valore fuori dominio nell'altro triangolo.
            if any(float(v) < -1e-12 or float(v) > 1 + 1e-12 for v in (x, y)):
                raise ValueError(f"Dissimilarita' fuori dall'intervallo [0,1]: ({i + 1}, {j + 1}).")
            if i == j:
                # Una diagonale numericamente nulla è riportata esattamente a 0.
                matrice[i][i] = 0.0
            else:
                # Scarti di arrotondamento entro la tolleranza sono ricondotti
                # a un unico valore; scarti maggiori sono già stati rifiutati.
                # L'output è così esattamente simmetrico, non solo 'quasi'.
                media = math.fsum((float(x), float(y))) / 2.0
                valore = min(1.0, max(0.0, media))
                matrice[i][j] = valore
                matrice[j][i] = valore

    if non_disponibili:
        esempi = "; ".join(
            f"righe {i + 1} ({etichette[i]}) e {j + 1} ({etichette[j]})"
            for i, j in non_disponibili[:6]
        )
        messaggio = (
            f"Non posso generare una matrice completa: {len(non_disponibili)} "
            f"coppie non hanno alcun contributo valido. Esempi: {esempi}. "
            "Rivedi le scelte sui mancanti, le colonne o le misure; "
            "nessuna distanza verra' inventata."
        )
        problema = {
            "gravita": "bloccante",
            "ambito": "matrice",
            "nome": "Coppie senza contributi",
            "idPercorso": None,
            "colonne": [],
            "messaggio": (
                f"{len(non_disponibili)} coppie non hanno alcun contributo "
                "locale definito e non possono ricevere una dissimilarita'."
            ),
            "decisioniPossibili": [
                "Rivedi i mancanti e la strategia scelta nei blocchi coinvolti.",
                "Valuta misure compatibili o una selezione diversa di righe e colonne.",
                "Imputa valori soltanto con una procedura motivata e confermata.",
            ],
        }
        raise IncompatibilitaCalcolo(messaggio, {
            "fase": "calcolo",
            "numeroBloccanti": 1,
            "numeroAvvisi": 0,
            "bloccanti": [problema],
            "nonBloccanti": [],
            "numeroCoppieNonConfrontabili": len(non_disponibili),
            # Indici 1-based; l'array etichette preserva l'eventuale duplicazione.
            # La lista completa resta esportabile senza riempire la matrice con zeri.
            "coppieNonConfrontabili": [
                [i + 1, j + 1] for i, j in non_disponibili
            ],
            "etichette": list(etichette),
        })

    coppie = [float(matrice[i][j]) for i in range(n) for j in range(i + 1, n)]
    zeri = sum(v <= 1e-12 for v in coppie)
    profili: dict[tuple[float, ...], list[int]] = {}
    for i, riga in enumerate(matrice):
        chiave = tuple(round(float(v), 10) for v in riga)
        profili.setdefault(chiave, []).append(i)
    gruppi_profili_uguali = [
        [etichette[i] for i in indici]
        for indici in profili.values() if len(indici) > 1
    ]
    avvisi: list[str] = []
    if zeri:
        avvisi.append(
            f"{zeri} coppie di righe distinte hanno dissimilarita' zero; "
            "possono essere indistinguibili con le caratteristiche selezionate."
        )
    if gruppi_profili_uguali:
        avvisi.append(
            f"{len(gruppi_profili_uguali)} gruppi di righe hanno profili "
            "di dissimilarita' identici."
        )
    if coppie and all(v <= 1e-12 for v in coppie):
        avvisi.append("Tutte le dissimilarita' tra righe distinte sono nulle.")
    return {
        "coppieTotali": len(coppie),
        # Se esistessero coppie non disponibili, il validatore avrebbe
        # gia' bloccato la matrice finale prima di questo punto.
        "coppieNonDisponibili": 0,
        "coppieZeroDistinte": zeri,
        "distribuzioneDissimilarita": _diagnostica_distribuzione_finale(coppie),
        "gruppiProfiliIdentici": gruppi_profili_uguali,
        "avvisi": avvisi,
    }



def _analisi_copertura_non_confrontabili(
    componenti: list[dict[str, Any]],
    coppie: list[list[int]],
) -> dict[str, Any]:
    """Spiega quali blocchi non forniscono contributi alle coppie scoperte.

    Una riga assente dal blocco (ad es. esclusione completa) è diversa
    da una coppia locale non definita su due righe presenti. Il report
    aggrega TUTTE le coppie; ne dettaglia soltanto le prime dodici,
    mantenendo l'elenco integrale separato nel rapporto d'errore.
    """
    per_blocco: list[dict[str, Any]] = [
        {
            "idPercorso": componente["percorso"]["idPercorso"],
            "titolo": componente["percorso"]["titolo"],
            "colonne": list(componente["percorso"]["colonne"]),
            "coppieConRigaAssente": 0,
            "coppieLocalmenteIndefinite": 0,
        }
        for componente in componenti
    ]
    esempi: list[dict[str, Any]] = []
    for uno, due in coppie:
        i, j = uno - 1, due - 1
        dettagli: list[dict[str, str]] = []
        for k, componente in enumerate(componenti):
            posizione_i = componente["posizioni"].get(i)
            posizione_j = componente["posizioni"].get(j)
            if posizione_i is None or posizione_j is None:
                motivo = "riga_assente"
                per_blocco[k]["coppieConRigaAssente"] += 1
            elif componente["matrice"][posizione_i][posizione_j] is None:
                motivo = "locale_indefinita"
                per_blocco[k]["coppieLocalmenteIndefinite"] += 1
            else:
                # In un errore di copertura nessun percorso può fornire
                # una distanza locale: segnaliamo un'incoerenza interna.
                raise ValueError(
                    "Diagnostica incoerente: una coppia dichiarata priva "
                    "di contributi ha una distanza locale definita."
                )
            if len(esempi) < 12:
                dettagli.append({
                    "idPercorso": componente["percorso"]["idPercorso"],
                    "titolo": componente["percorso"]["titolo"],
                    "motivo": motivo,
                })
        if len(esempi) < 12:
            esempi.append({"righe": [uno, due], "blocchi": dettagli})
    return {
        "numeroCoppie": len(coppie),
        "perBlocco": per_blocco,
        "esempi": esempi,
        "nota": (
            "Riga assente: almeno una osservazione non appartiene al "
            "risultato locale del blocco. Distanza locale indefinita: "
            "entrambe le righe sono presenti, ma la misura non produce "
            "una dissimilarita' utilizzabile per la coppia. "
            "Nessuno dei due casi equivale a distanza zero."
        ),
    }


def _diagnostica_sensibilita_pesi(
    componenti: list[dict[str, Any]],
    matrice_finale: list[list[float]],
) -> dict[str, Any]:
    """Esperimenti CONTROFATTUALI sui pesi, senza modificare la matrice.

    Per ciascun blocco k si valutano w_k/2 e 2*w_k, lasciando tutte
    le dissimilarita' locali e le loro normalizzazioni invariate.
    Il confronto per omissione (w_k -> 0) viene definito solo se un
    altro blocco rimane disponibile per la coppia considerata.
    """
    n = len(matrice_finale)
    totale_coppie = n * (n - 1) // 2
    if not componenti:
        raise ValueError("La diagnostica richiede almeno un blocco di confronto.")
    schede: list[dict[str, Any]] = []
    for componente in componenti:
        percorso = componente["percorso"]
        schede.append({
            "idPercorso": percorso["idPercorso"],
            "titolo": percorso["titolo"],
            "pesoOriginale": float(percorso["pesoAggregazione"]),
            "coppieDefinite": 0,
            "coppieNonDisponibili": 0,
            "coppieLocaliNulle": 0,
            "coppieLocaliPositive": 0,
            "sommaLocali": 0.0,
            "fattoreMezzo": {"somma": 0.0, "massima": 0.0, "coppieVariate": 0},
            "fattoreDoppio": {"somma": 0.0, "massima": 0.0, "coppieVariate": 0},
            "senzaBlocco": {
                "somma": 0.0, "massima": 0.0, "coppieVariate": 0,
                "coppieConfrontabili": 0,
                "coppieSenzaAltroContributo": 0,
            },
        })
    for i in range(n):
        for j in range(i + 1, n):
            disponibili: list[tuple[int, float, float]] = []
            for k, componente in enumerate(componenti):
                posizione_i = componente["posizioni"].get(i)
                posizione_j = componente["posizioni"].get(j)
                valore = (
                    componente["matrice"][posizione_i][posizione_j]
                    if posizione_i is not None and posizione_j is not None
                    else None
                )
                scheda = schede[k]
                if valore is None:
                    scheda["coppieNonDisponibili"] += 1
                    continue
                distanza = float(valore)
                peso = scheda["pesoOriginale"]
                scheda["coppieDefinite"] += 1
                scheda["sommaLocali"] += distanza
                if abs(distanza) <= 1e-12:
                    scheda["coppieLocaliNulle"] += 1
                else:
                    scheda["coppieLocaliPositive"] += 1
                disponibili.append((k, peso, distanza))
            somma_pesi = sum(w for _, w, _ in disponibili)
            if somma_pesi <= 0:
                raise ValueError("La sensibilità non è definita per coppie prive di blocchi.")
            somma_pesata = sum(w * v for _, w, v in disponibili)
            base = float(matrice_finale[i][j])
            for k, peso, valore in disponibili:
                scheda = schede[k]
                for fattore, chiave in ((0.5, "fattoreMezzo"), (2.0, "fattoreDoppio")):
                    alternativo = (
                        somma_pesata + (fattore - 1) * peso * valore
                    ) / (somma_pesi + (fattore - 1) * peso)
                    variazione = abs(alternativo - base)
                    dati = scheda[chiave]
                    dati["somma"] += variazione
                    dati["massima"] = max(dati["massima"], variazione)
                    if variazione > 1e-12:
                        dati["coppieVariate"] += 1
                altri_pesi = somma_pesi - peso
                senza = scheda["senzaBlocco"]
                if altri_pesi > 0:
                    alternativo = (somma_pesata - peso * valore) / altri_pesi
                    variazione = abs(alternativo - base)
                    senza["coppieConfrontabili"] += 1
                    senza["somma"] += variazione
                    senza["massima"] = max(senza["massima"], variazione)
                    if variazione > 1e-12:
                        senza["coppieVariate"] += 1
                else:
                    senza["coppieSenzaAltroContributo"] += 1

    rapporti: list[dict[str, Any]] = []
    blocchi_nulli: list[dict[str, Any]] = []
    for scheda in schede:
        numero = scheda["coppieDefinite"]
        scheda["distanzaLocaleMedia"] = scheda.pop("sommaLocali") / numero if numero else None
        scheda["sempreNulloSulleCoppieDefinite"] = (
            numero > 0 and scheda["coppieLocaliPositive"] == 0
        )
        for nome, fattore in (("fattoreMezzo", 0.5), ("fattoreDoppio", 2.0)):
            valore = scheda.pop(nome)
            scheda[nome] = {
                "fattorePeso": fattore,
                "coppieVariate": valore["coppieVariate"],
                "variazioneMediaAssoluta": (
                    valore["somma"] / totale_coppie if totale_coppie else 0.0
                ),
                "variazioneMassimaAssoluta": valore["massima"],
            }
        senza = scheda["senzaBlocco"]
        n_confrontabili = senza["coppieConfrontabili"]
        scheda["senzaBlocco"] = {
            "coppieConfrontabili": n_confrontabili,
            "coppieSenzaAltroContributo": senza["coppieSenzaAltroContributo"],
            "coppieVariate": senza["coppieVariate"],
            "variazioneMediaAssoluta": (
                senza["somma"] / n_confrontabili if n_confrontabili else None
            ),
            "variazioneMassimaAssoluta": (
                senza["massima"] if n_confrontabili else None
            ),
        }
        rapporti.append(scheda)
        if scheda["sempreNulloSulleCoppieDefinite"]:
            blocchi_nulli.append({
                "idPercorso": scheda["idPercorso"],
                "titolo": scheda["titolo"],
                "peso": scheda["pesoOriginale"],
                "coppieDefinite": numero,
                "coppieNonDisponibili": scheda["coppieNonDisponibili"],
                "coppieConAltriBlocchi": n_confrontabili,
                "attenuazioneMassimaRimuovendolo": (
                    senza["massima"] if n_confrontabili else None
                ),
            })
    return {
        "metodo": (
            "Modifica un solo peso globale per volta con i fattori 0.5 e 2, "
            "mantenendo invariati dati, misure, pesi interni, mancanti e "
            "normalizzazioni locali. Le variazioni assolute sono misurate "
            "rispetto alla matrice scelta. La media per i fattori positivi "
            "usa tutte le coppie distinte (incluse quelle senza il blocco, "
            "la cui variazione è zero). La rimozione ipotetica w=0 usa "
            "solo coppie con almeno un altro contributo disponibile e "
            "non costituisce un peso ammissibile nel piano corrente."
        ),
        "tolleranzaZero": 1e-12,
        "coppieTotali": totale_coppie,
        "numeroBlocchi": len(componenti),
        "perBlocco": rapporti,
        "blocchiSempreNulli": blocchi_nulli,
    }


def calcola_matrice(risultato: dict[str, Any], interpretazione: dict[str, Any]) -> dict[str, Any]:
    piano = crea_piano_confronto(risultato, interpretazione)
    percorsi = piano["percorsi"]
    if not piano["completo"] or not percorsi:
        raise ValueError("Completa le informazioni richieste prima di calcolare la matrice.")
    if not all(percorso["calcolo"]["disponibile"] for percorso in percorsi):
        raise ValueError("Almeno un percorso non è ancora calcolabile.")

    def calcola(percorso: dict[str, Any]) -> dict[str, Any]:
        if percorso["tipo"] == "gower":
            return calcola_matrice_gower(risultato, interpretazione)
        if percorso["tipo"] == "numerico":
            return calcola_matrice_numerica(risultato, interpretazione)
        return _calcola_matrice_specializzata(risultato, interpretazione, percorso)

    if len(percorsi) == 1:
        # Anche un unico percorso deve produrre valori finali in [0,1].
        try:
            singolo = calcola(percorsi[0])
            normalizzata, descrizione, diagnostica_normalizzazione = (
                _normalizza_per_aggregazione_con_diagnostica(
                    singolo, percorsi[0]["normalizzazione"]
                )
            )
        except ValueError as errore:
            if isinstance(errore, IncompatibilitaCalcolo):
                raise
            percorso = percorsi[0]
            problema = {
                "gravita": "bloccante",
                "ambito": "percorso",
                "nome": percorso["titolo"],
                "idPercorso": percorso["idPercorso"],
                "colonne": list(percorso["colonne"]),
                "messaggio": str(errore),
                "decisioniPossibili": _azioni_rapporto_problema(str(errore)),
            }
            raise IncompatibilitaCalcolo(
                f"Il blocco “{percorso['titolo']}” non è calcolabile: {errore}",
                _rapporto_errori_percorsi([problema]),
            ) from errore
        etichette = singolo["etichette"]
        try:
            singolo["diagnosticaFinale"] = _valida_matrice_finale(normalizzata, etichette)
        except IncompatibilitaCalcolo as errore:
            coppie = errore.rapportoProblemi.get("coppieNonConfrontabili", [])
            if coppie:
                errore.rapportoProblemi["analisiCopertura"] = (
                    _analisi_copertura_non_confrontabili(
                        [{
                            "percorso": percorsi[0],
                            "matrice": normalizzata,
                            # Nel ramo con un solo percorso, gli indici
                            # del rapporto sono riferiti alle righe rimaste,
                            # non alle posizioni del CSV originario.
                            "posizioni": {
                                indice: indice for indice in range(len(normalizzata))
                            },
                        }],
                        coppie,
                    )
                )
            raise
        singolo["diagnosticaFinale"]["sensibilitaPesi"] = _diagnostica_sensibilita_pesi(
            [{
                "percorso": percorsi[0],
                "matrice": normalizzata,
                "posizioni": {
                    indice: posizione
                    for posizione, indice in enumerate(singolo["indiciRighe"])
                },
            }], normalizzata
        )
        for nullo in singolo["diagnosticaFinale"]["sensibilitaPesi"]["blocchiSempreNulli"]:
            singolo["diagnosticaFinale"]["avvisi"].append(
                f"Il blocco “{nullo['titolo']}” ha distanza locale nulla in "
                f"tutte le {nullo['coppieDefinite']} coppie confrontabili. "
                "È un contributo valido, non un valore mancante."
            )
        singolo["diagnosticaMancantiSemantici"] = piano["diagnosticaMancantiSemantici"]
        singolo["pesaturaGlobale"] = piano["pesaturaGlobale"]
        if diagnostica_normalizzazione["coppieSaturate"]:
            singolo["diagnosticaFinale"]["avvisi"].append(
                f"{diagnostica_normalizzazione['coppieSaturate']} coppie sono "
                "saturate a 1 dalla normalizzazione robusta."
            )
        singolo["normalizzazioneFinale"] = diagnostica_normalizzazione
        singolo["matrice"] = normalizzata
        singolo["limiteAggregazione"] = 1.0
        singolo["csv"] = crea_csv(
            ["Riga", *etichette],
            [[etichetta, *riga] for etichetta, riga in zip(etichette, normalizzata)],
        )
        singolo["nota"] += f" Normalizzazione finale: {descrizione}."
        return singolo

    n = len(risultato["originale"]["righe"])
    if n > 1000:
        raise ValueError("La matrice completa è limitata a 1000 righe per evitare di bloccare il browser.")
    componenti: list[dict[str, Any]] = []
    errori_percorsi: list[dict[str, Any]] = []
    for percorso in percorsi:
        try:
            risultato_percorso = calcola(percorso)
            matrice_normalizzata, normalizzazione, diagnostica_normalizzazione = (
                _normalizza_per_aggregazione_con_diagnostica(
                    risultato_percorso, percorso["normalizzazione"]
                )
            )
        except ValueError as errore:
            errori_percorsi.append({
                "gravita": "bloccante",
                "ambito": "percorso",
                "nome": percorso["titolo"],
                "idPercorso": percorso["idPercorso"],
                "colonne": list(percorso["colonne"]),
                "messaggio": str(errore),
                "decisioniPossibili": _azioni_rapporto_problema(str(errore)),
            })
            continue
        componenti.append({
            "percorso": percorso,
            "risultato": risultato_percorso,
            "matrice": matrice_normalizzata,
            "posizioni": {
                indice_originale: posizione
                for posizione, indice_originale in enumerate(risultato_percorso["indiciRighe"])
            },
            "normalizzazione": normalizzazione,
            "diagnosticaNormalizzazione": diagnostica_normalizzazione,
        })
    if errori_percorsi:
        raise IncompatibilitaCalcolo(
            f"Il calcolo è sospeso: {len(errori_percorsi)} blocchi presentano "
            "problemi. Consulta il rapporto completo e modifica le scelte.",
            _rapporto_errori_percorsi(errori_percorsi),
        )

    matrice_finale: list[list[float | None]] = [[0.0 for _ in range(n)] for _ in range(n)]
    coppie_con_copertura_parziale = 0
    coppie_con_solo_un_percorso = 0
    contributi_minimi = len(componenti)
    contributi_massimi = 0
    for i in range(n):
        for k in range(i + 1, n):
            contributi_validi: list[tuple[float, float]] = []
            percorsi_disponibili = 0
            for componente in componenti:
                posizione_i = componente["posizioni"].get(i)
                posizione_k = componente["posizioni"].get(k)
                if posizione_i is None or posizione_k is None:
                    continue
                valore = componente["matrice"][posizione_i][posizione_k]
                if valore is None:
                    continue
                peso = float(componente["percorso"]["pesoAggregazione"])
                contributi_validi.append((peso, float(valore)))
                percorsi_disponibili += 1
            contributi_minimi = min(contributi_minimi, percorsi_disponibili)
            contributi_massimi = max(contributi_massimi, percorsi_disponibili)
            if 0 < percorsi_disponibili < len(componenti):
                coppie_con_copertura_parziale += 1
                if percorsi_disponibili == 1:
                    coppie_con_solo_un_percorso += 1
            distanza = _media_pesata_stabile(contributi_validi)
            matrice_finale[i][k] = distanza
            matrice_finale[k][i] = distanza

    etichette = _etichette_righe(risultato, interpretazione)
    try:
        diagnostica_finale = _valida_matrice_finale(matrice_finale, etichette)
    except IncompatibilitaCalcolo as errore:
        coppie = errore.rapportoProblemi.get("coppieNonConfrontabili", [])
        if coppie:
            errore.rapportoProblemi["analisiCopertura"] = (
                _analisi_copertura_non_confrontabili(componenti, coppie)
            )
        raise
    diagnostica_finale["sensibilitaPesi"] = _diagnostica_sensibilita_pesi(
        componenti, matrice_finale
    )
    for nullo in diagnostica_finale["sensibilitaPesi"]["blocchiSempreNulli"]:
        attenuazione = nullo["attenuazioneMassimaRimuovendolo"]
        diagnostica_finale["avvisi"].append(
            f"Il blocco “{nullo['titolo']}” (peso {nullo['peso']:.6g}) "
            f"ha distanza locale nulla in tutte le {nullo['coppieDefinite']} "
            "coppie in cui contribuisce. È mantenuto nel denominatore e "
            "può attenuare le distanze degli altri blocchi."
            + (
                f" Scostamento massimo dalla matrice corrente, rimuovendolo "
                f"solo per le coppie ancora confrontabili: {attenuazione:.6g}."
                if attenuazione is not None else
                " La sua rimozione lascerebbe tutte queste coppie senza "
                "altri contributi."
            )
        )
    diagnostica_finale["coppieCoperturaParziale"] = coppie_con_copertura_parziale
    diagnostica_finale["coppieConSoloUnPercorso"] = coppie_con_solo_un_percorso
    diagnostica_finale["minContributiPerCoppia"] = contributi_minimi
    diagnostica_finale["maxContributiPerCoppia"] = contributi_massimi
    if coppie_con_copertura_parziale:
        diagnostica_finale["avvisi"].append(
            f"{coppie_con_copertura_parziale} coppie usano meno di "
            f"{len(componenti)} blocchi; {coppie_con_solo_un_percorso} "
            "coppie sono confrontate con un solo blocco. "
            "La media pesata è rinormalizzata sui soli contributi "
            "effettivamente disponibili: non si è sostituita alcuna "
            "distanza mancante con zero. Le coppie possono utilizzare "
            "informazioni differenti."
        )
    for componente in componenti:
        numero_sature = componente["diagnosticaNormalizzazione"]["coppieSaturate"]
        if numero_sature:
            diagnostica_finale["avvisi"].append(
                f"Percorso “{componente['percorso']['titolo']}”: "
                f"{numero_sature} coppie locali saturate a 1 dalla scala robusta."
            )
    righe_csv = [[etichetta, *riga] for etichetta, riga in zip(etichette, matrice_finale)]
    contributi = [
        {
            "idPercorso": componente["percorso"]["idPercorso"],
            "titolo": componente["percorso"]["titolo"],
            "metodo": componente["percorso"]["metodo"],
            "peso": componente["percorso"]["pesoAggregazione"],
            "numeroCaratteristiche": componente["percorso"]["numeroCaratteristiche"],
            "originePeso": componente["percorso"]["originePesoAggregazione"],
            "normalizzazione": componente["normalizzazione"],
            "diagnosticaNormalizzazione": componente["diagnosticaNormalizzazione"],
        }
        for componente in componenti
    ]
    dettagli = "; ".join(
        f"{contributo['titolo']}: peso {format(float(contributo['peso']), '.6g')}, "
        f"{contributo['normalizzazione']}"
        for contributo in contributi
    )
    return {
        "metodo": "Dissimilarità complessiva pesata",
        "colonne": list(dict.fromkeys(
            nome for percorso in percorsi for nome in percorso["colonne"]
        )),
        "etichette": etichette,
        "matrice": matrice_finale,
        "diagnosticaFinale": diagnostica_finale,
        "diagnosticaMancantiSemantici": piano["diagnosticaMancantiSemantici"],
        "pesaturaGlobale": piano["pesaturaGlobale"],
        "indiciRighe": list(range(n)),
        "limiteAggregazione": 1.0,
        "contributi": contributi,
        "csv": crea_csv(["Riga", *etichette], righe_csv),
        "nota": (
            "Ogni percorso è riportato nell’intervallo [0,1] e la matrice finale è "
            "la media pesata dei contributi disponibili per ciascuna coppia. "
            + piano["pesaturaGlobale"]["descrizione"] + " "
            + dettagli + "."
        ),
    }


def _valore_csv(valore: Any) -> Any:
    if valore is None:
        return ""
    if isinstance(valore, (int, float)) and not isinstance(valore, bool):
        pulito = 0 if abs(float(valore)) < 1e-14 else float(valore)
        return format(pulito, ".12g").replace(".", ",")
    return str(valore)


def crea_csv(intestazioni: list[str], righe: list[list[Any]]) -> str:
    destinazione = io.StringIO(newline="")
    scrittore = csv.writer(destinazione, delimiter=";", lineterminator="\n")
    for riga in [intestazioni, *righe]:
        scrittore.writerow([_valore_csv(valore) for valore in riga])
    return destinazione.getvalue().rstrip("\n")


RAPPORTO_FORMATO = "laboratorio-misure/rapporto-calcolo"
RAPPORTO_VERSIONE_SCHEMA = 1
RAPPORTO_REVISIONE_MOTORE = "20261114-fase7-sensibilita-pesi-v2"


def _normalizza_json_rapporto(dato: Any) -> Any:
    """JSON standard: valori non finiti nelle sole diagnostiche sono espliciti.

    Un risultato di matrice non finito viene invece rifiutato dal calcolo
    e dal validatore, prima di poter costruire il rapporto.
    """
    if isinstance(dato, float) and not math.isfinite(dato):
        return {"valoreNonFinito": (
            "NaN" if math.isnan(dato) else
            "+Inf" if dato > 0 else "-Inf"
        )}
    if isinstance(dato, dict):
        return {str(chiave): _normalizza_json_rapporto(valore)
                for chiave, valore in dato.items()}
    if isinstance(dato, (list, tuple)):
        return [_normalizza_json_rapporto(valore) for valore in dato]
    return dato


def crea_rapporto_calcolo(
    testo: str, scelte: list[dict[str, str]],
    interpretazione: dict[str, Any], nome_file: str = "dati.csv",
) -> dict[str, Any]:
    """Rapporto autosufficiente per ricalcolare la matrice sulla stessa logica.

    Una sola origine dei calcoli: piano e matrice vengono ricalcolati con
    gli stessi parametri, senza dedurre un significato dalle etichette.
    Il file contiene intenzionalmente l'intero CSV originale.
    """
    if not isinstance(scelte, list) or not isinstance(interpretazione, dict):
        raise ValueError("Le scelte e le risposte per il rapporto devono essere valide.")
    if not isinstance(nome_file, str):
        raise ValueError("Il nome del CSV deve essere una stringa.")
    tabella = leggi_csv(testo)
    preparata = prepara_tabella(tabella, scelte)
    piano = crea_piano_confronto(preparata, interpretazione)
    if not piano["completo"]:
        raise ValueError(
            "Il rapporto completo è disponibile solo per un piano calcolabile. "
            "Risolvi prima le domande e gli avvisi bloccanti."
        )
    risultato = calcola_matrice(preparata, interpretazione)
    dati_configurazione = {
        "sceltePreprocessing": scelte,
        "risposteQuestionario": interpretazione,
    }
    canonica = json.dumps(
        dati_configurazione, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    )
    output = {
        "formato": RAPPORTO_FORMATO,
        "versioneSchema": RAPPORTO_VERSIONE_SCHEMA,
        "revisioneMotore": RAPPORTO_REVISIONE_MOTORE,
        "avvisoRiservatezza": (
            "Questo file incorpora tutte le celle e le intestazioni del CSV "
            "originale, comprese eventuali informazioni personali. "
            "Conservalo e condividilo soltanto con destinatari autorizzati."
        ),
        "riproducibilita": {
            "condizione": (
                "A parità di CSV originale, opzioni confermate e revisione "
                "della logica di calcolo, il piano e la matrice si possono "
                "rigenerare. Versioni future del motore possono utilizzare "
                "regole differenti; i controlli numerici rispettano le "
                "tolleranze della validazione documentata."
            ),
            "sha256CsvOriginale": hashlib.sha256(
                testo.encode("utf-8")
            ).hexdigest(),
            "sha256Configurazione": hashlib.sha256(
                canonica.encode("utf-8")
            ).hexdigest(),
            "procedura": (
                "leggi_csv(csvOriginale); prepara_tabella(tabella, "
                "sceltePreprocessing); crea_piano_confronto(preparata, "
                "risposteQuestionario); calcola_matrice(preparata, "
                "risposteQuestionario)."
            ),
        },
        "sorgente": {
            "nomeFile": nome_file,
            "csvOriginale": testo,
            "separatoreRilevato": tabella["separatore"],
            "intestazioni": tabella["intestazioni"],
            "numeroRighe": len(tabella["righe"]),
            "numeroColonne": len(tabella["intestazioni"]),
        },
        "configurazione": dati_configurazione,
        "preprocessing": {
            "riepilogo": preparata["riepilogo"],
            "analisiColonne": preparata["colonne"],
            "nota": (
                "Le trasformazioni effettive utilizzate dalle singole misure "
                "sono specificate nel campo piano.percorsi.preelaborazione; "
                "non tutte le misure impiegano la tabella riscalata."
            ),
        },
        "piano": piano,
        "risultato": {
            "metodo": risultato["metodo"],
            "etichette": risultato["etichette"],
            "colonne": risultato["colonne"],
            "matrice": risultato["matrice"],
            "csvMatrice": risultato["csv"],
            "nota": risultato["nota"],
            "contributi": risultato.get("contributi", []),
            "pesaturaGlobale": risultato.get("pesaturaGlobale", piano["pesaturaGlobale"]),
            "diagnosticaFinale": risultato["diagnosticaFinale"],
            "diagnosticaMancantiSemantici": risultato["diagnosticaMancantiSemantici"],
            "normalizzazioneFinale": risultato.get("normalizzazioneFinale"),
            "limiteAggregazione": risultato.get("limiteAggregazione"),
        },
    }
    return _normalizza_json_rapporto(output)


def crea_rapporto_json(
    testo: str, scelte_json: str = "[]", interpretazione_json: str = "{}",
    nome_file: str = "dati.csv",
) -> str:
    try:
        scelte = json.loads(scelte_json or "[]")
        interpretazione = json.loads(interpretazione_json or "{}")
        rapporto = crea_rapporto_calcolo(
            testo, scelte, interpretazione, nome_file,
        )
        return json.dumps(
            {"ok": True, "rapporto": rapporto}, ensure_ascii=False,
            separators=(",", ":"), allow_nan=False,
        )
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as errore:
        return json.dumps(
            {"ok": False, "errore": str(errore)}, ensure_ascii=False,
            separators=(",", ":"), allow_nan=False,
        )


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


def crea_piano_json(testo: str, scelte_json: str = "[]", interpretazione_json: str = "{}") -> str:
    try:
        scelte = json.loads(scelte_json or "[]")
        interpretazione = json.loads(interpretazione_json or "{}")
        risultato = prepara_tabella(leggi_csv(testo), scelte)
        piano = crea_piano_confronto(risultato, interpretazione)
        return json.dumps({"ok": True, "piano": piano}, ensure_ascii=False, separators=(",", ":"))
    except (ValueError, TypeError, json.JSONDecodeError) as errore:
        return json.dumps({"ok": False, "errore": str(errore)}, ensure_ascii=False, separators=(",", ":"))


def calcola_gower_json(testo: str, scelte_json: str = "[]", interpretazione_json: str = "{}") -> str:
    try:
        scelte = json.loads(scelte_json or "[]")
        interpretazione = json.loads(interpretazione_json or "{}")
        risultato = prepara_tabella(leggi_csv(testo), scelte)
        gower = calcola_matrice_gower(risultato, interpretazione)
        return json.dumps({"ok": True, "gower": gower}, ensure_ascii=False, separators=(",", ":"))
    except (ValueError, TypeError, json.JSONDecodeError) as errore:
        return json.dumps({"ok": False, "errore": str(errore)}, ensure_ascii=False, separators=(",", ":"))


def calcola_matrice_json(testo: str, scelte_json: str = "[]", interpretazione_json: str = "{}") -> str:
    try:
        scelte = json.loads(scelte_json or "[]")
        interpretazione = json.loads(interpretazione_json or "{}")
        risultato = prepara_tabella(leggi_csv(testo), scelte)
        matrice = calcola_matrice(risultato, interpretazione)
        return json.dumps({"ok": True, "matrice": matrice}, ensure_ascii=False, separators=(",", ":"))
    except IncompatibilitaCalcolo as errore:
        return json.dumps(
            {"ok": False, "errore": str(errore),
             "rapportoProblemi": errore.rapportoProblemi},
            ensure_ascii=False, separators=(",", ":"), allow_nan=False,
        )
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as errore:
        return json.dumps({"ok": False, "errore": str(errore)}, ensure_ascii=False, separators=(",", ":"))
