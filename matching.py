"""Matching: turn a rich free-text profile into a vector and pair people by
cosine similarity. Runs entirely inside the enclave on decrypted plaintext;
no profile text ever leaves this process.

Embedding
---------
For the hackathon we ship a dependency-light deterministic embedder (hashed
bag-of-words -> L2-normalised vector). It is good enough to demonstrate that
"more detail -> better signal", runs instantly on CPU, and needs no model
download. PRODUCTION: swap `embed()` for a sentence-transformers model bundled
inside the enclave image (e.g. all-MiniLM-L6-v2). The rest of the pipeline is
unchanged. See HANDOFF.md.
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


def match_round(
    profiles: list[tuple[str, np.ndarray]],
    threshold: float = 0.15,
) -> tuple[list[tuple[str, str, float]], list[str]]:
    """Greedy global pairing by descending similarity.

    Args:
        profiles: list of (user_id, vector).
        threshold: minimum cosine for a pair to be offered. Below it we leave
            people unmatched on purpose -- "no great match" is a feature, not a
            bug (the anti-scroll thesis).

    Returns:
        (pairs, unmatched_ids) where pairs = [(a, b, score), ...].
    """
    candidates = []
    for i in range(len(profiles)):
        for j in range(i + 1, len(profiles)):
            uid_a, va = profiles[i]
            uid_b, vb = profiles[j]
            score = cosine(va, vb)
            if score >= threshold:
                candidates.append((score, uid_a, uid_b))
    candidates.sort(reverse=True)

    used: set[str] = set()
    pairs: list[tuple[str, str, float]] = []
    for score, a, b in candidates:
        if a in used or b in used:
            continue
        used.add(a)
        used.add(b)
        pairs.append((a, b, round(score, 4)))

    all_ids = {uid for uid, _ in profiles}
    unmatched = sorted(all_ids - used)
    return pairs, unmatched
