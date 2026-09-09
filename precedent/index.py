"""Cohort index. Precomputed so a lookup is milliseconds, not a study.

The published barrier to point-of-care cohort tools is that cohort generation takes weeks,
which is untenable in a 15-minute visit. The answer is not a faster query — it is to do the
work earlier. We trade freshness (cohorts as of the last batch) for latency. For this
question freshness is not the binding constraint.

numpy exact search is used here because the population is small and it is easier to verify.
FAISS with an IVF index is the production choice and the interface below does not change.
"""
from __future__ import annotations
import numpy as np
from .state import MemberState

MIN_COHORT_SIZE = 30   # below this we return NO RESULT. This is the credibility of the tool.
MIN_PATH_SIZE = 10     # a path taken by fewer than this is folded into "other"
SIM_THRESHOLD = 0.93   # cosine similarity floor for "like this one"


class CohortIndex:
    def __init__(self, states: list[MemberState]):
        self.states = states
        self.ids = [s.member_id for s in states]
        M = np.vstack([s.vector for s in states])
        norms = np.linalg.norm(M, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        self._M = M / norms                       # unit vectors -> dot product is cosine

    def query(self, state: MemberState, *, k: int = 500,
              threshold: float = SIM_THRESHOLD) -> tuple[list[int], np.ndarray]:
        """Return indices of similar members, excluding the query member itself."""
        v = state.vector
        n = np.linalg.norm(v) or 1.0
        sims = self._M @ (v / n)
        order = np.argsort(-sims)[:k]
        keep = [int(i) for i in order
                if sims[i] >= threshold and self.ids[i] != state.member_id]
        return keep, sims[keep] if keep else np.array([])
