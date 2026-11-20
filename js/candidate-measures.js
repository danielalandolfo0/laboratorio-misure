"use strict";

// Catalogo semantico delle misure candidate. Il catalogo non esegue ancora
// i calcoli: l'ammissibilità numerica va ricontrollata prima di usarle.
window.LearningMeasureCatalog = Object.freeze({
  numeric: {label:"Quantità numeriche", measures:["manhattan","euclidean","chebyshev","minkowski","mahalanobis"]},
  abundance: {label:"Quantità non negative per componenti", measures:["manhattan","euclidean","chebyshev","minkowski","mahalanobis","canberra","braycurtis"]},
  parts: {label:"Parti di uno stesso totale", measures:["braycurtis","hellinger","jensen_shannon","aitchison"]},
  profile_ratio: {label:"Profili con proporzioni simili", measures:["cosine"]},
  profile_trend: {label:"Profili con lo stesso andamento", measures:["correlation"]},
  binary: {label:"Stati 0/1 equivalenti", measures:["hamming"]},
  presence: {label:"Presenze e assenze", measures:["jaccard"]},
  nominal: {label:"Categorie senza ordine", measures:["matching"]},
  ordinal: {label:"Livelli ordinati", measures:["ordinal_steps"]},
  temporal_aligned: {label:"Serie temporali allineate", measures:["pointwise","cosine","correlation","dtw","lcss"]},
  temporal_flexible: {label:"Serie temporali non allineate", measures:["dtw","lcss"]},
  text: {label:"Testo o sequenze di simboli", measures:["exact","hamming_string","levenshtein","damerau_levenshtein"]},
  mixed: {label:"Colonne di tipi diversi", measures:["gower"]}
});
