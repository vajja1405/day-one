"""Member state vector — the thing we match on.

Every feature here is a choice I have to defend out loud, so each one carries its reason.
A clinician would choose differently, and that is the main thing I would want corrected by
someone who has seen real data.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np

# (name, why it is in the vector)
STATE_FEATURES: list[tuple[str, str]] = [
    ("age_band",        "utilisation and risk both scale steeply with age in an MA population"),
    ("ckd",             "chronic condition; drives both cost and care-path choice"),
    ("chf",             "the most admission-driving condition in this population"),
    ("copd",            "frequent exacerbation pattern, distinct care pathway"),
    ("diabetes",        "comorbid with CKD; changes management of everything else"),
    ("afib",            "anticoagulation decisions dominate the care path"),
    ("med_count",       "polypharmacy is a severity proxy independent of diagnosis list"),
    ("egfr",            "kidney function; the single most informative continuous lab here"),
    ("egfr_declining",  "direction of travel matters more than level for referral decisions"),
    ("prior_admissions","past utilisation is the strongest single predictor of future"),
    ("care_gaps",       "engagement proxy; correlates with follow-through on any plan"),
]
FEATURE_NAMES = [f for f, _ in STATE_FEATURES]

# Weights: clinical drivers matter more than counts when deciding who is "like" whom.
_WEIGHTS = np.array([1.0, 1.4, 1.6, 1.2, 1.2, 1.0, 0.8, 1.5, 1.3, 1.4, 0.6])


@dataclass
class MemberState:
    member_id: str
    raw: dict[str, float]
    vector: np.ndarray = field(repr=False)
    severity: float = 0.0   # kept OUT of the match vector; used only for adjustment strata

    @property
    def severity_stratum(self) -> str:
        if self.severity < 0.33:
            return "low"
        if self.severity < 0.66:
            return "moderate"
        return "high"


def _norm(raw: dict[str, float]) -> np.ndarray:
    """Scale each feature to roughly 0-1 so no single feature dominates the distance."""
    v = np.array([
        (raw["age_band"] - 65) / 25.0,
        raw["ckd"], raw["chf"], raw["copd"], raw["diabetes"], raw["afib"],
        min(raw["med_count"], 15) / 15.0,
        1.0 - min(max(raw["egfr"], 10), 90) / 90.0,   # inverted: lower eGFR = higher value
        raw["egfr_declining"],
        min(raw["prior_admissions"], 4) / 4.0,
        min(raw["care_gaps"], 6) / 6.0,
    ], dtype=float)
    return v * _WEIGHTS


def build_state(member_id: str, raw: dict[str, float]) -> MemberState:
    v = _norm(raw)
    # Severity is a deliberately separate construct. If it were inside the match vector we
    # would match sick people to sick people and then be unable to adjust for severity —
    # the confounder would be baked into the comparison.
    severity = float(np.clip(
        0.30 * raw["chf"] + 0.20 * raw["ckd"] + 0.15 * raw["copd"]
        + 0.20 * min(raw["prior_admissions"], 4) / 4.0
        + 0.15 * (1.0 - min(max(raw["egfr"], 10), 90) / 90.0), 0, 1))
    return MemberState(member_id=member_id, raw=raw, vector=v, severity=severity)
