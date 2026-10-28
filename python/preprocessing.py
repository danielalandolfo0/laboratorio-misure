"""Analisi e riscalamento di tabelle CSV eseguiti interamente in Python."""

from __future__ import annotations

import csv
import datetime as dt
import io
import json
import math
import re
from typing import Any


MANCANTI = {"", "na", "n/a", "null", "?"}
INVALIDO = object()
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
        interi = False
        numeri: list[float] = []
        if colonna["tipo"] == "numerica" and colonna.get("valoriNumerici"):
            numeri = [v for v in colonna["valoriNumerici"] if isinstance(v, (int, float))]
            interi = bool(numeri) and all(float(v).is_integer() for v in numeri)
        piccola_scala = (
            interi
            and 2 < distinti <= 7
            and min(numeri) >= 0
            and max(numeri) <= 10
            and max(numeri) - min(numeri) <= 10
        )

        if nome_identificativo:
            ruolo, motivo = "identificativo", "Il titolo della colonna fa pensare a un codice identificativo."
        elif nome_data or quota_date >= 0.8:
            ruolo, motivo = "data", "Il titolo o i valori fanno pensare a date o orari."
        elif colonna["tipo"] == "binaria":
            ruolo = "presenza" if parole & PAROLE_PRESENZA else "binaria"
            motivo = "La colonna contiene soltanto due valori, 0 e 1."
        elif colonna["tipo"] == "non_numerica" and distinti <= min(12, max(4, round(len(osservati) * 0.25))):
            ruolo, motivo = "categoria", "Poche etichette si ripetono in molte righe."
        elif colonna["tipo"] == "non_numerica":
            ruolo, motivo = "testo", "La colonna contiene molte scritte differenti."
        elif colonna["tipo"] == "numerica" and (bool(parole & PAROLE_LIVELLO) or piccola_scala):
            ruolo, motivo = "livello", "Sono presenti pochi valori interi ordinabili."
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
        "questionario": prepara_questionario(tabella, colonne),
    }


ETICHETTE_RUOLO = {
    "quantita": "Quantità misurata", "livello": "Livello ordinato",
    "presenza": "Presenza o assenza", "binaria": "Risposta con due possibilità",
    "categoria": "Categoria senza ordine", "identificativo": "Codice identificativo",
    "data": "Data o orario", "testo": "Testo o sequenza",
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
        risposta = interpretazione.get("ordineLivelli", "")
        if risposta == "no":
            misura, motivo = "Uguale o diverso", "I livelli sono trattati come etichette perché l’ordine non ha significato."
        elif risposta == "si" and tipo == "non_numerica":
            misura, motivo = "Da decidere", "Per livelli testuali occorre specificare esplicitamente l’ordine delle etichette."
            avvisi.append("L’ordine dei livelli testuali non può essere ricavato senza una conferma.")
            stato = "da_completare"
        elif risposta == "si":
            misura, motivo = "Differenza tra ranghi normalizzata", "Tiene conto dell’ordine dei livelli e non della distanza numerica grezza."
        else:
            misura, motivo = "Da decidere", "Occorre sapere se l’ordine dei livelli ha significato."
            avvisi.append("Rispondi alla domanda sull’ordine dei livelli.")
            stato = "da_completare"
    elif ruolo == "presenza":
        if tipo != "binaria":
            misura, motivo = "Da decidere", "Una presenza o assenza deve essere rappresentata da due valori."
            avvisi.append("Controlla il significato o il tipo di dato della colonna.")
            stato = "da_completare"
        else:
            risposta = interpretazione.get("zeriCondivisi", "")
            if risposta == "si":
                misura, motivo = "Disaccordo binario", "Sia le presenze sia le assenze condivise contribuiscono alla somiglianza."
            elif risposta == "no":
                misura, motivo = "Confronto asimmetrico di Jaccard", "Le assenze condivise vengono ignorate; contano soprattutto le presenze."
            else:
                misura, motivo = "Da decidere", "Occorre sapere se due assenze condivise debbano contare come somiglianza."
                avvisi.append("Rispondi alla domanda sulle assenze condivise.")
                stato = "da_completare"
    elif ruolo == "binaria":
        if tipo != "binaria":
            misura, motivo = "Da decidere", "Una risposta binaria deve essere rappresentata da due valori."
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
    elif ruolo == "testo":
        misura = "Distanza di Levenshtein normalizzata"
        motivo = "Confronta quante modifiche servono per trasformare un testo nell’altro, tenendo conto della lunghezza."
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


def _blocco_gruppo(gruppo: dict[str, Any], membri: list[str], analisi_per_nome: dict[str, dict[str, Any]], interpretazione: dict[str, Any]) -> dict[str, Any]:
    """Traduce un gruppo di colonne in una sola regola di confronto."""
    nome = str(gruppo.get("nome") or "Gruppo senza nome")
    tipo_gruppo = gruppo.get("tipo", "altro")
    avvisi: list[str] = []
    stato = "pronto"
    etichetta = {"ripetute": "Misurazioni dello stesso profilo", "tempo": "Osservazioni successive nel tempo",
                 "parti": "Parti dello stesso totale", "altro": "Gruppo di caratteristiche"}.get(tipo_gruppo, "Gruppo di caratteristiche")

    if len(membri) < 2:
        misura, motivo = "Da completare", "Un gruppo deve contenere almeno due colonne."
        avvisi.append("Assegna almeno due colonne al gruppo oppure rimuovilo.")
        stato = "da_completare"
    else:
        tipi = {analisi_per_nome[m]["tipo"] for m in membri if m in analisi_per_nome}
        numerico = bool(tipi) and tipi <= {"numerica", "numerica_costante"}
        if tipo_gruppo in {"ripetute", "tempo", "parti"} and not numerico:
            misura, motivo = "Da decidere", "Questa interpretazione richiede colonne numeriche."
            avvisi.append("Controlla il tipo di dato delle colonne del gruppo.")
            stato = "da_completare"
        elif tipo_gruppo == "ripetute":
            risposta = interpretazione.get(f"somiglianza-{gruppo.get('id')}", "")
            scelte = {
                "valori_vicini": ("Distanza tra coordinate", "Confronta i valori coordinata per coordinata e riassume il gruppo in un solo contributo."),
                "proporzioni": ("Dissimilarità coseno", "Confronta la direzione dei profili, riducendo l’effetto della loro grandezza complessiva."),
                "andamento": ("Dissimilarità di Pearson", "Confronta come i valori crescono e diminuiscono rispetto al livello medio del profilo."),
                "ordine": ("Dissimilarità di Spearman", "Confronta l’ordinamento interno delle coordinate dei due profili."),
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
                misura, motivo = "Dynamic Time Warping", "Permette di allineare andamenti simili che avvengono con un piccolo ritardo."
            elif risposta == "no":
                misura, motivo = "Distanza punto per punto", "Confronta soltanto osservazioni rilevate negli stessi istanti."
            else:
                misura, motivo = "Da decidere", "Occorre sapere se piccoli ritardi temporali debbano essere tollerati."
                avvisi.append(f"Rispondi alla domanda sul ritardo nel gruppo “{nome}”.")
                stato = "da_completare"
        elif tipo_gruppo == "parti":
            risposta = interpretazione.get(f"totale-{gruppo.get('id')}", "")
            if risposta == "si":
                misura, motivo = "Distanza composizionale di Aitchison", "Confronta le proporzioni tra le parti, non la grandezza totale."
                if any(analisi_per_nome[m].get("statistiche", {}).get("zeri", 0) > 0 for m in membri):
                    avvisi.append("Sono presenti zeri: prima del calcolo servirà stabilire come trattarli.")
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

    return {"nome": nome, "colonne": membri, "interpretazione": etichetta, "misura": misura,
            "motivo": motivo, "stato": stato, "avvisi": avvisi}


RUOLI_GOWER = {"quantita", "livello", "presenza", "binaria", "categoria", "data"}


def _crea_percorsi(
    indipendenti: list[str],
    gruppi_con_blocco: list[tuple[dict[str, Any], dict[str, Any]]],
    ruoli: dict[str, str],
    analisi_per_nome: dict[str, dict[str, Any]],
    interpretazione: dict[str, Any],
    blocchi_per_nome: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Separa il piano nei tre percorsi concordati, senza combinarne i risultati."""
    percorsi: list[dict[str, Any]] = []
    standard = [nome for nome in indipendenti if ruoli[nome] in RUOLI_GOWER]
    separati = [nome for nome in indipendenti if nome not in standard]

    if standard:
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
            if len(standard) == 1:
                metodo = "Differenza assoluta"
                motivo = "Con una sola caratteristica numerica, euclidea e Manhattan coincidono."
            elif ha_estremi:
                metodo = "Distanza di Manhattan"
                motivo = "Usa la tabella riscalata e limita il predominio delle differenze più grandi."
            else:
                metodo = "Distanza euclidea"
                motivo = "Usa la tabella riscalata e combina le differenze delle caratteristiche numeriche."
            percorsi.append({
                "tipo": "numerico", "titolo": "Caratteristiche numeriche indipendenti",
                "colonne": standard, "metodo": metodo, "origine": "Tabella di lavoro",
                "motivo": motivo, "stato": stato_blocchi,
            })
        else:
            risposta_estremi = interpretazione.get("significatoEstremi", "")
            stato = stato_blocchi
            if ha_estremi and risposta_estremi == "reali":
                metodo = "Dissimilarità di Gower robusta"
                motivo = "Le caratteristiche sono di tipo diverso e gli outlier reali non devono comprimere tutte le altre differenze."
            elif ha_estremi and risposta_estremi in {"errori", "controllare"}:
                metodo = "Gower dopo il controllo dei dati"
                motivo = "Prima del calcolo occorre correggere o verificare i valori estremi segnalati."
                stato = "da_completare"
            else:
                metodo = "Dissimilarità di Gower classica"
                motivo = "Combina quantità, categorie, livelli e variabili binarie con contributi confrontabili."
            percorsi.append({
                "tipo": "gower", "titolo": "Caratteristiche indipendenti di tipo misto",
                "colonne": standard, "metodo": metodo,
                "origine": "Valori originali; Gower applica il proprio riscalamento",
                "motivo": motivo, "stato": stato,
            })

    for nome in separati:
        blocco = blocchi_per_nome[nome]
        percorsi.append({
            "tipo": "separato", "titolo": ETICHETTE_RUOLO.get(ruoli[nome], "Confronto separato"),
            "colonne": [nome], "metodo": blocco["misura"], "origine": "Confronto separato",
            "motivo": blocco["motivo"], "stato": blocco["stato"],
        })

    for gruppo, blocco in gruppi_con_blocco:
        percorsi.append({
            "tipo": "gruppo", "titolo": blocco["nome"], "colonne": blocco["colonne"],
            "metodo": blocco["misura"], "origine": blocco["interpretazione"],
            "motivo": blocco["motivo"], "stato": blocco["stato"],
        })
    return percorsi


def crea_piano_confronto(risultato: dict[str, Any], interpretazione: dict[str, Any]) -> dict[str, Any]:
    """Costruisce un piano verificabile senza calcolare ancora le distanze."""
    if not isinstance(interpretazione, dict):
        raise ValueError("Le risposte del questionario non sono valide.")
    profili = risultato["questionario"]["colonne"]
    analisi_per_nome = {colonna["nome"]: colonna for colonna in risultato["colonne"]}
    risposte_colonne = interpretazione.get("colonne", {})
    assegnazioni = interpretazione.get("assegnazioni", {})
    gruppi = interpretazione.get("gruppi", [])
    gruppi_per_id = {gruppo.get("id"): gruppo for gruppo in gruppi}
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
            blocco = _blocco_gruppo(gruppo, membri, analisi_per_nome, interpretazione)
            blocchi.append(blocco)
            gruppi_con_blocco.append((gruppo, blocco))

    blocchi_per_nome = {blocco["nome"]: blocco for blocco in blocchi_indipendenti}
    percorsi = _crea_percorsi(
        indipendenti, gruppi_con_blocco, ruoli, analisi_per_nome,
        interpretazione, blocchi_per_nome,
    )

    avvisi: list[str] = []
    if not interpretazione.get("riga"):
        avvisi.append("Indica che cosa rappresenta ogni riga.")
    if not blocchi:
        avvisi.append("Includi almeno una colonna nel confronto.")
    if any(analisi_per_nome[n]["mancanti"] > 0 for n in incluse) and interpretazione.get("significatoMancanti") in {None, "", "ignoto"}:
        avvisi.append("Indica che cosa significano le caselle vuote nelle colonne incluse.")
    incluse_con_estremi = any(analisi_per_nome[n].get("statistiche", {}).get("estremi", 0) > 0 for n in incluse)
    if incluse_con_estremi and interpretazione.get("significatoEstremi") in {None, "", "ignoto"}:
        avvisi.append("Indica se i valori molto lontani dagli altri sono plausibili.")
    elif incluse_con_estremi and interpretazione.get("significatoEstremi") in {"errori", "controllare"}:
        avvisi.append("Controlla i valori estremi prima di calcolare le distanze.")

    completo = bool(blocchi) and not avvisi and all(b["stato"] != "da_completare" for b in blocchi)
    return {
        "blocchi": blocchi, "percorsi": percorsi, "avvisi": avvisi,
        "completo": completo, "conteggioBlocchi": len(blocchi),
        "conteggioPercorsi": len(percorsi),
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


def _metadati_gower(
    risultato: dict[str, Any],
    interpretazione: dict[str, Any],
    percorso: dict[str, Any],
) -> list[dict[str, Any]]:
    tabella = risultato["originale"]
    analisi_per_nome = {colonna["nome"]: colonna for colonna in risultato["colonne"]}
    profili = {profilo["nome"]: profilo for profilo in risultato["questionario"]["colonne"]}
    risposte = interpretazione.get("colonne", {})
    robusta = percorso["metodo"] == "Dissimilarità di Gower robusta"
    metadati: list[dict[str, Any]] = []

    for nome in percorso["colonne"]:
        indice = tabella["intestazioni"].index(nome)
        grezzi = [riga[indice] for riga in tabella["righe"]]
        ruolo = risposte.get(nome, {}).get("ruolo", profili[nome]["ruoloSuggerito"])
        analisi = analisi_per_nome[nome]

        if ruolo == "quantita":
            valori = [leggi_numero(valore, tabella["separatore"]) for valore in grezzi]
            if any(valore is INVALIDO for valore in valori):
                raise ValueError(f"La colonna “{nome}” contiene valori non numerici.")
            osservati = [float(valore) for valore in valori if valore is not None]
            intervallo = max(osservati) - min(osservati) if osservati else 0
            if robusta and analisi.get("statistiche", {}).get("iqr", 0) > 0:
                scala = 7 * analisi["statistiche"]["iqr"]
            else:
                scala = intervallo
            metadati.append({"nome": nome, "tipo": "numerica", "valori": valori, "scala": scala, "limita": robusta})
        elif ruolo == "data":
            valori = [_leggi_data(valore) for valore in grezzi]
            osservati = sorted({valore for valore in valori if valore is not None})
            if interpretazione.get("usoDate") == "ordine":
                massimo = max(1, len(osservati) - 1)
                mappa = {valore: indice / massimo for indice, valore in enumerate(osservati)}
                codificati = [None if valore is None else mappa[valore] for valore in valori]
                metadati.append({"nome": nome, "tipo": "numerica", "valori": codificati, "scala": 1, "limita": False})
            else:
                scala = osservati[-1] - osservati[0] if osservati else 0
                metadati.append({"nome": nome, "tipo": "numerica", "valori": valori, "scala": scala, "limita": False})
        elif ruolo == "livello" and interpretazione.get("ordineLivelli") == "si":
            numeri = [leggi_numero(valore, tabella["separatore"]) for valore in grezzi]
            if any(valore is INVALIDO for valore in numeri if valore is not None):
                raise ValueError(f"Specifica l’ordine dei livelli della colonna “{nome}”.")
            livelli = sorted({float(valore) for valore in numeri if valore is not None})
            massimo = max(1, len(livelli) - 1)
            mappa = {valore: indice / massimo for indice, valore in enumerate(livelli)}
            valori = [None if valore is None else mappa[float(valore)] for valore in numeri]
            metadati.append({"nome": nome, "tipo": "numerica", "valori": valori, "scala": 1, "limita": False})
        else:
            valori = [None if mancante(valore) else str(valore) for valore in grezzi]
            asimmetrica = ruolo == "presenza" and interpretazione.get("zeriCondivisi") == "no"
            metadati.append({"nome": nome, "tipo": "nominale", "valori": valori, "asimmetrica": asimmetrica})
    return metadati


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
            somma = 0.0
            peso = 0
            for variabile in metadati:
                a = variabile["valori"][i]
                b = variabile["valori"][k]
                if a is None or b is None:
                    continue
                if variabile["tipo"] == "nominale":
                    if variabile.get("asimmetrica") and float(a) == 0 and float(b) == 0:
                        continue
                    contributo = 0.0 if a == b else 1.0
                else:
                    scala = variabile["scala"]
                    contributo = 0.0 if scala == 0 else abs(float(a) - float(b)) / scala
                    if variabile.get("limita"):
                        contributo = min(contributo, 1.0)
                somma += contributo
                peso += 1
            distanza = None if peso == 0 else somma / peso
            matrice[i][k] = distanza
            matrice[k][i] = distanza

    etichette = _etichette_righe(risultato, interpretazione)
    righe_csv = [[etichetta, *riga] for etichetta, riga in zip(etichette, matrice)]
    nota = (
        "Per le quantità, Gower robusta usa l’ampiezza tra Q1−3·IQR e Q3+3·IQR; "
        "i contributi superiori a 1 vengono limitati a 1."
        if percorso["metodo"] == "Dissimilarità di Gower robusta"
        else "Per le quantità, Gower classica divide la differenza assoluta per l’intervallo osservato."
    )
    return {
        "metodo": percorso["metodo"], "colonne": percorso["colonne"],
        "etichette": etichette, "matrice": matrice,
        "csv": crea_csv(["Riga", *etichette], righe_csv), "nota": nota,
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
