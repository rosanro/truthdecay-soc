"""RAG minimo: recuperacion lexica top-k sobre el corpus del caso.

Sin dependencias externas. Para el escalado (E7) esto se sustituye por File Search
de Gemini o embeddings; el resto del harness no cambia, porque `retrieve` devuelve
`AgentDoc` (vista redactada) independientemente del backend.
"""
from __future__ import annotations

import math
import re
from typing import List

from core.types import AgentDoc


def tokenize(s: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", (s or "").lower())


def _bm25_scores(query: str, docs: List[AgentDoc], k1: float = 1.5, b: float = 0.75):
    q_terms = tokenize(query)
    doc_tokens = [tokenize(d.content) for d in docs]
    n = len(docs)
    avgdl = (sum(len(t) for t in doc_tokens) / n) if n else 0.0
    # document frequency
    df = {}
    for toks in doc_tokens:
        for t in set(toks):
            df[t] = df.get(t, 0) + 1
    scores = []
    for toks in doc_tokens:
        dl = len(toks)
        tf = {}
        for t in toks:
            tf[t] = tf.get(t, 0) + 1
        s = 0.0
        for t in set(q_terms):
            if t not in tf:
                continue
            idf = math.log(1 + (n - df.get(t, 0) + 0.5) / (df.get(t, 0) + 0.5))
            denom = tf[t] + k1 * (1 - b + b * (dl / avgdl if avgdl else 0))
            s += idf * (tf[t] * (k1 + 1)) / (denom if denom else 1)
        scores.append(s)
    return scores


def retrieve(query: str, docs: List[AgentDoc], k: int | None = None) -> List[AgentDoc]:
    """Devuelve los k documentos mas relevantes (orden descendente de score).

    Con corpus pequenos (2-3 docs por caso) k por defecto = todos, pero el orden
    refleja relevancia real, no el orden del fichero.
    """
    if not docs:
        return []
    scores = _bm25_scores(query, docs)
    order = sorted(range(len(docs)), key=lambda i: -scores[i])
    if k is not None:
        order = order[:k]
    return [docs[i] for i in order]
