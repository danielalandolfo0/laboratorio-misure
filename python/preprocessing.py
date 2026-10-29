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

ETICHETTE_TRASFORMAZIONE = {
    "zscore": "Z-score",
    "robusto": "Scala robusta (mediana e IQR)",
    "minmax": "Min–max",
    "maxabs": "Max-abs",
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
    tipo_quantita = interpretazione.get("tipoQuantita", "")
    politica_preelaborazione = "originale"

    metodi_automatici = {
        analisi_per_nome[nome].get("metodo", "nessuno")
        for nome in nomi
    }
    riscalamento_rilevato = bool(
        metodi_automatici & {"zscore", "robusto", "maxabs", "minmax"}
    )

    # Le vecchie risposte restano interpretabili; nel nuovo flusso il sito decide
    # automaticamente quando le dispersioni sono chiaramente differenti.
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
    elif riscalamento_rilevato:
        politica_preelaborazione = "trasformazioni_candidate"
    elif tipo_quantita == "stesso":
        politica_preelaborazione = "originale"
    elif tipo_quantita in {"diverse", "ignoto"} or confronto == "ignoto":
        politica_preelaborazione = "zscore_prudenziale"
    else:
        avvisi.append(
            "Indica se le colonne misurano lo stesso tipo di quantità; "
            "questa informazione non può essere ricavata con certezza dai soli numeri."
        )
        stato = "da_completare"

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
        aggregazione = interpretazione.get("aggregazioneScarti", "")
        mappa = {
            "lineare": "manhattan",
            "quadratica": "euclidean",
            "massimo": "chebyshev",
            "minkowski": "minkowski",
        }
        if aggregazione == "ignoto" or confronto == "ignoto":
            ha_estremi = any(
                analisi_per_nome[nome].get("statistiche", {}).get("estremi", 0) > 0
                for nome in nomi
            )
            aggregazione = "lineare" if ha_estremi else "quadratica"
        id_misura = mappa.get(aggregazione, "euclidean")
        if aggregazione == "":
            avvisi.append("Indica che cosa debba rendere due righe molto diverse.")
            stato = "da_completare"
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

        dipendenza = interpretazione.get("dipendenzaCoordinate", "no") if len(nomi) >= 2 else "no"
        if dipendenza == "si":
            id_misura = "mahalanobis"
            politica_preelaborazione = "originale"
            if numero_istanze <= len(nomi) or not _covarianza_empirica_invertibile(nomi, analisi_per_nome):
                avvisi.append(
                    "La covarianza empirica non è invertibile: servono più righe complete, "
                    "l’eliminazione delle dipendenze lineari oppure una regolarizzazione esplicita."
                )
                stato = "da_completare"

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
    }


def _politica_mancanti(
    nomi: list[str],
    analisi_per_nome: dict[str, dict[str, Any]],
    tipo_percorso: str,
) -> dict[str, Any]:
    """Dichiara, senza impliciti, come il percorso tratta i valori mancanti."""
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
        metodo = metodo_forzato or analisi_per_nome[nome].get("metodo", "nessuno")
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


def _completa_specifica_percorso(
    percorso: dict[str, Any],
    analisi_per_nome: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Aggiunge origine, trasformazioni, mancanti e disponibilità del calcolo."""
    tipo = percorso["tipo"]
    nomi = percorso["colonne"]
    if tipo == "numerico":
        politica = percorso.get("politicaPreelaborazione", "trasformazioni_candidate")
        if politica == "originale":
            preelaborazione = _preelaborazione_originale(
                "La misura confronta direttamente i valori originali e incorpora già la normalizzazione richiesta."
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
        preelaborazione = _preelaborazione_originale(
            "Il gruppo è confrontato come un unico oggetto. Un riscalamento separato "
            "delle colonne potrebbe modificarne forma, direzione o ordinamento."
        )
    else:
        preelaborazione = _preelaborazione_originale(
            "Il confronto separato usa la rappresentazione coerente con il significato "
            "della singola caratteristica."
        )

    mancanti = _politica_mancanti(nomi, analisi_per_nome, tipo)
    if not mancanti["pronta"]:
        percorso["stato"] = "da_completare"
    percorso["preelaborazione"] = preelaborazione
    percorso["origine"] = preelaborazione["etichettaOrigine"]
    percorso["mancanti"] = mancanti
    calcolabile = tipo in {"gower", "numerico"} and percorso["stato"] != "da_completare"
    percorso["calcolo"] = {
        "disponibile": calcolabile,
        "descrizione": (
            "La matrice è calcolabile nel sito."
            if calcolabile
            else "Il piano è esplicito; il calcolo di questa famiglia sarà collegato nel modulo successivo."
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
                "motivo": motivo, "stato": stato,
            })

    for nome in separati:
        blocco = blocchi_per_nome[nome]
        percorsi.append({
            "tipo": "separato", "titolo": ETICHETTE_RUOLO.get(ruoli[nome], "Confronto separato"),
            "colonne": [nome], "metodo": blocco["misura"],
            "motivo": blocco["motivo"], "stato": blocco["stato"],
        })

    for gruppo, blocco in gruppi_con_blocco:
        percorsi.append({
            "tipo": "gruppo", "titolo": blocco["nome"], "colonne": blocco["colonne"],
            "metodo": blocco["misura"],
            "motivo": blocco["motivo"], "stato": blocco["stato"],
        })
    return [_completa_specifica_percorso(percorso, analisi_per_nome) for percorso in percorsi]


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
        interpretazione, blocchi_per_nome, len(risultato["originale"]["righe"]),
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
    return {
        "blocchi": blocchi, "percorsi": percorsi, "avvisi": avvisi,
        "completo": completo, "conteggioBlocchi": len(blocchi),
        "conteggioPercorsi": len(percorsi), "versioneContratto": 1,
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
    if metodo == "costante" or stats.get("deviazione") == 0:
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
    raise ValueError(f"Trasformazione numerica non riconosciuta: {metodo}.")


def _cholesky(matrice: list[list[float]]) -> list[list[float]]:
    p = len(matrice)
    scala = max((abs(v) for riga in matrice for v in riga), default=1.0)
    tolleranza = max(1.0, scala) * 1e-12
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


def _covarianza(righe: list[list[float]]) -> list[list[float]]:
    n = len(righe)
    p = len(righe[0])
    if n <= p:
        raise ValueError("Per Mahalanobis servono più righe complete del numero di colonne.")
    medie = [sum(riga[j] for riga in righe) / n for j in range(p)]
    return [[
        sum((riga[j] - medie[j]) * (riga[k] - medie[k]) for riga in righe) / (n - 1)
        for k in range(p)
    ] for j in range(p)]


def _distanza_numerica(
    x: list[float],
    y: list[float],
    id_misura: str,
    parametri: dict[str, Any],
    cholesky_covarianza: list[list[float]] | None = None,
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
    if id_misura == "standardized_euclidean":
        scale = [float(scala) for scala in parametri["scale"]]
        return math.sqrt(sum((scarto / scala) ** 2 for scarto, scala in zip(scarti, scale)))
    if id_misura == "mahalanobis":
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
        denominatore = sum(a + b for a, b in zip(x, y))
        return None if denominatore == 0 else sum(scarti) / denominatore
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
    indici = [tabella["intestazioni"].index(nome) for nome in nomi]
    metodi = {passo["colonna"]: passo["metodo"] for passo in percorso["preelaborazione"]["passi"]}

    righe_numeriche: list[list[float]] = []
    for riga in tabella["righe"]:
        vettore: list[float] = []
        for nome, indice in zip(nomi, indici):
            metodo = metodi.get(nome, "nessuno")
            valore = _trasforma_per_percorso(riga[indice], analisi_per_nome[nome], metodo)
            if valore is None:
                raise ValueError("Il percorso numerico non può essere calcolato finché contiene valori mancanti.")
            vettore.append(valore)
        righe_numeriche.append(vettore)

    id_misura = percorso["idMisura"]
    parametri = dict(percorso.get("parametri", {}))
    if id_misura == "standardized_euclidean":
        parametri["scale"] = [analisi_per_nome[nome]["statistiche"]["deviazione"] for nome in nomi]
    fattore_cholesky = None
    if id_misura == "mahalanobis":
        fattore_cholesky = _cholesky(_covarianza(righe_numeriche))

    n = len(righe_numeriche)
    matrice: list[list[float | None]] = [[0.0 for _ in range(n)] for _ in range(n)]
    for i in range(n):
        for k in range(i + 1, n):
            distanza = _distanza_numerica(
                righe_numeriche[i], righe_numeriche[k], id_misura, parametri, fattore_cholesky
            )
            matrice[i][k] = distanza
            matrice[k][i] = distanza

    etichette = _etichette_righe(risultato, interpretazione)
    righe_csv = [[etichetta, *riga] for etichetta, riga in zip(etichette, matrice)]
    origine = percorso["preelaborazione"]["etichettaOrigine"].lower()
    nota = f"Calcolata sulle colonne {', '.join(nomi)} usando {origine}."
    if id_misura == "mahalanobis":
        nota += " La covarianza empirica considera il pattern con cui le colonne variano insieme; nessuna colonna è stata eliminata."
    return {
        "metodo": percorso["metodo"], "colonne": nomi,
        "etichette": etichette, "matrice": matrice,
        "csv": crea_csv(["Riga", *etichette], righe_csv), "nota": nota,
    }


def calcola_matrice(risultato: dict[str, Any], interpretazione: dict[str, Any]) -> dict[str, Any]:
    piano = crea_piano_confronto(risultato, interpretazione)
    calcolabili = [percorso for percorso in piano["percorsi"] if percorso["calcolo"]["disponibile"]]
    if len(calcolabili) != 1:
        raise ValueError("Il calcolo diretto richiede un unico percorso completo e calcolabile.")
    if calcolabili[0]["tipo"] == "gower":
        return calcola_matrice_gower(risultato, interpretazione)
    if calcolabili[0]["tipo"] == "numerico":
        return calcola_matrice_numerica(risultato, interpretazione)
    raise ValueError("Questo tipo di matrice non è ancora calcolabile nel sito.")


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
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as errore:
        return json.dumps({"ok": False, "errore": str(errore)}, ensure_ascii=False, separators=(",", ":"))
