"use strict";

// Catalogo semantico delle misure candidate. Il catalogo non esegue ancora
// i calcoli: l'ammissibilità numerica va ricontrollata prima di usarle.
window.LearningMeasureCatalog = Object.freeze({
  numeric: {label:"Quantità numeriche", measures:["manhattan","euclidean","chebyshev","minkowski","mahalanobis"]},
  abundance: {label:"Quantità non negative per componenti", measures:["manhattan","euclidean","chebyshev","minkowski","mahalanobis","canberra","braycurtis"]},
  parts: {label:"Parti di uno stesso totale", measures:["braycurtis","hellinger","jensen_shannon","aitchison"]},
  binary: {label:"Stati 0/1", measures:["hamming","matching","rogers_tanimoto"]},
  presence: {label:"Presenze e assenze", measures:["hamming","jaccard","dice"]},
  nominal: {label:"Categorie senza ordine", measures:["matching"]},
  ordinal: {label:"Livelli ordinati", measures:["ordinal_steps"]},
  temporal: {label:"Misure successive nel tempo", measures:["pointwise","dtw","lcss"]},
  text: {label:"Testo o sequenze di simboli", measures:["exact","hamming_string","levenshtein","damerau_levenshtein"]},
  mixed: {label:"Colonne di tipi diversi", measures:["gower"]}
});
