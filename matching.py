"""Cheap prefilter for the matching pipeline.

Running the heavy AI matcher (dating_matching_ai.DatingMatchingAI) on every
possible pair is O(N^2) cross-encoder calls -- too slow. So this module turns
each free-text profile into a fast vector and uses cheap cosine similarity to
pick a *shortlist* of plausible candidate pairs. The expensive AI matcher then
only runs on that shortlist. See `candidate_pairs()`.

Embedding
---------
We ship a dependency-light deterministic embedder (hashed bag-of-words -> L2-
normalised vector). It runs instantly on CPU and needs no model download. It is
intentionally only a *coarse* filter; the real compatibility decision is made
later by the AI matcher on the raw text.
"""
from __future__ import annotations

import math
import re
from typing import Iterable

import numpy as np

DIM = 512
_token_re = re.compile(r"[a-z0-9']+")


def _tokens(text: str) -> list[str]:
    return _token_re.findall(text.lower())


def embed(text: str) -> np.ndarray:
    """Deterministic hashed bag-of-words embedding, L2-normalised.

    PRODUCTION: replace body with `return model.encode(text)`.
    """
    vec = np.zeros(DIM, dtype=np.float32)
    toks = _tokens(text)
    if not toks:
        return vec
    for tok in toks:
        h = hash(_stable(tok))
        idx = h % DIM
        sign = 1.0 if (h >> 16) & 1 else -1.0
        vec[idx] += sign
    norm = np.linalg.norm(vec)
    return vec / norm if norm > 0 else vec


def _stable(s: str) -> int:
    # Python's hash() is salted per-process; use a stable hash for repeatable
    # embeddings across restarts.
    h = 1469598103934665603
    for ch in s.encode():
        h ^= ch
        h = (h * 1099511628211) & 0xFFFFFFFFFFFFFFFF
    return h


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b))  # vectors are already L2-normalised


def candidate_pairs(
    profiles: list[tuple[str, np.ndarray]],
    top_k: int = 5,
    floor: float = 0.0,
) -> list[tuple[str, str, float]]:
    """Cheap shortlist of pairs worth running the expensive AI matcher on.

    For each person we keep their `top_k` most cosine-similar others (above
    `floor`), then union those into a deduplicated set of unordered pairs. This
    bounds the number of expensive AI calls to roughly N*top_k/2 instead of the
    full N*(N-1)/2.

    The cosine scan itself is still O(N^2), but each cosine is a single cheap
    numpy dot product -- the cost we are trying to avoid is the AI cross-encoder
    downstream, not this. (For very large N, swap this scan for an approximate
    nearest-neighbour index; the pipeline is otherwise unchanged.)

    Args:
        profiles: list of (user_id, vector). Vectors are L2-normalised.
        top_k: how many nearest neighbours to keep per person.
        floor: minimum cosine for a neighbour to be considered at all.

    Returns:
        [(uid_a, uid_b, cosine), ...] unique unordered pairs, best cosine first.
        `cosine` is only a coarse prefilter score, not the final verdict.
    """
    best: dict[tuple[str, str], float] = {}
    n = len(profiles)
    for i in range(n):
        uid_i, vi = profiles[i]
        neighbours: list[tuple[float, str]] = []
        for j in range(n):
            if i == j:
                continue
            uid_j, vj = profiles[j]
            score = cosine(vi, vj)
            if score >= floor:
                neighbours.append((score, uid_j))
        neighbours.sort(reverse=True)
        for score, uid_j in neighbours[:top_k]:
            key = tuple(sorted((uid_i, uid_j)))  # type: ignore[assignment]
            if score > best.get(key, -1.0):
                best[key] = score

    pairs = [(a, b, round(s, 4)) for (a, b), s in best.items()]
    pairs.sort(key=lambda t: t[2], reverse=True)
    return pairs
