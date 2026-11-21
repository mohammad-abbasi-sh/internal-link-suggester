"""TF-IDF vectors and cosine similarity (standard library only).

Sublinear term frequency (1 + log(tf)) and smoothed IDF, the same
weighting scikit-learn's TfidfVectorizer uses by default -- reimplemented
here so the tool has zero dependencies.
"""

from __future__ import annotations

import math
from collections import Counter


def tfidf_vectors(documents: list[list[str]]) -> list[dict[str, float]]:
    """One sparse TF-IDF vector per document (token -> weight)."""
    n_docs = len(documents)
    if n_docs == 0:
        return []
    doc_freq: Counter[str] = Counter()
    term_counts: list[Counter[str]] = []
    for tokens in documents:
        counts = Counter(tokens)
        term_counts.append(counts)
        doc_freq.update(counts.keys())

    vectors: list[dict[str, float]] = []
    for counts in term_counts:
        vector: dict[str, float] = {}
        for term, count in counts.items():
            tf = 1.0 + math.log(count)  # sublinear tf
            idf = math.log((1.0 + n_docs) / (1.0 + doc_freq[term])) + 1.0
            vector[term] = tf * idf
        norm = math.sqrt(sum(weight * weight for weight in vector.values()))
        if norm > 0:
            vector = {term: weight / norm for term, weight in vector.items()}
        vectors.append(vector)
    return vectors


def cosine_similarity(vec_a: dict[str, float], vec_b: dict[str, float]) -> float:
    """Cosine similarity of two L2-normalized sparse vectors (0..1)."""
    if len(vec_a) > len(vec_b):
        vec_a, vec_b = vec_b, vec_a
    return sum(weight * vec_b.get(term, 0.0) for term, weight in vec_a.items())
