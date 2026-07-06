"""Bootstrap percentil de proporciones (IC). Sin numpy.

Con N pequeno los IC son anchos: se reportan como orientativos, coherente con §8 de la
memoria (la afirmacion primaria es de existencia + causalidad, no de tasa precisa).
"""
from __future__ import annotations

import random
from typing import List, Tuple


def bootstrap_ci(values: List[float], n_boot: int = 2000, alpha: float = 0.05,
                 seed: int = 0) -> Tuple[float, float, float]:
    """Devuelve (media, low, high) del IC percentil (1-alpha)."""
    vals = list(values)
    if not vals:
        return (0.0, 0.0, 0.0)
    rng = random.Random(seed)
    m = sum(vals) / len(vals)
    means = []
    k = len(vals)
    for _ in range(n_boot):
        sample = [vals[rng.randrange(k)] for _ in range(k)]
        means.append(sum(sample) / k)
    means.sort()
    lo = means[int((alpha / 2) * n_boot)]
    hi = means[int((1 - alpha / 2) * n_boot) - 1]
    return (m, lo, hi)
