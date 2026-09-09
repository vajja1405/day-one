"""Precedent — precomputed matched-cohort evidence at the point of care.

Answers "what happened to members like this one?" from a plan's own population.

Design commitments, in order of importance:
  1. It refuses. Below MIN_COHORT_SIZE it returns no result rather than a fragile number.
  2. It reports crude AND severity-adjusted rates side by side, because the crude number is
     often misleading and hiding that would make the tool dangerous.
  3. It is observational. Caveats are part of the payload, never a footnote.
"""
from .state import MemberState, build_state, STATE_FEATURES
from .index import CohortIndex, MIN_COHORT_SIZE, MIN_PATH_SIZE
from .outcomes import PrecedentReport, build_report

__all__ = ["MemberState", "build_state", "STATE_FEATURES", "CohortIndex",
           "MIN_COHORT_SIZE", "MIN_PATH_SIZE", "PrecedentReport", "build_report"]
