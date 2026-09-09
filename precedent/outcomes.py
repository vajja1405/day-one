"""Turn a matched cohort into an honest report.

Two numbers are always produced for every path: the CRUDE rate and the SEVERITY-ADJUSTED
rate. When they disagree materially the report says so in plain language, because the crude
number is the one a busy clinician will read first and it is often wrong.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
import numpy as np
from .index import CohortIndex, MIN_COHORT_SIZE, MIN_PATH_SIZE
from .state import MemberState

STRATA = ["low", "moderate", "high"]


@dataclass
class PathResult:
    label: str
    n: int
    share: float
    crude_admission_rate: float
    adjusted_admission_rate: float
    median_cost: float
    ci_low: float
    ci_high: float
    note: str = ""


@dataclass
class PrecedentReport:
    member_id: str
    cohort_size: int
    confidence: str                       # reportable | directional | insufficient
    reason: str = ""
    matched_on: list[str] = field(default_factory=list)
    adjusted_for: list[str] = field(default_factory=list)
    paths: list[PathResult] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)

    def to_dict(self):
        d = asdict(self)
        d["paths"] = [asdict(p) for p in self.paths]
        return d


def _wilson(k: int, n: int) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    z, p = 1.96, k / n
    d = 1 + z**2 / n
    c = (p + z**2 / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def build_report(state: MemberState, index: CohortIndex,
                 outcomes: list[dict]) -> PrecedentReport:
    idx, _ = index.query(state)
    n = len(idx)

    if n < MIN_COHORT_SIZE:
        return PrecedentReport(
            member_id=state.member_id, cohort_size=n, confidence="insufficient",
            reason=f"only {n} similar members found; minimum is {MIN_COHORT_SIZE}",
            caveats=["No result shown. A distribution over this few members would be noise."])

    rows = [outcomes[i] for i in idx]
    # Reference distribution across strata for the whole cohort — this is what we
    # standardise each path to, so paths are compared at the same severity mix.
    ref = np.array([sum(1 for r in rows if r["severity_stratum"] == s) for s in STRATA], float)
    ref = ref / ref.sum()

    paths: list[PathResult] = []
    for label in sorted({r["path"] for r in rows}):
        sub = [r for r in rows if r["path"] == label]
        if len(sub) < MIN_PATH_SIZE:
            continue
        k = sum(1 for r in sub if r["admitted_12mo"])
        crude = k / len(sub)

        # Direct standardisation onto the cohort's own severity mix.
        adj, used = 0.0, 0.0
        for w, s in zip(ref, STRATA):
            cell = [r for r in sub if r["severity_stratum"] == s]
            if cell:
                adj += w * (sum(1 for r in cell if r["admitted_12mo"]) / len(cell))
                used += w
        adj = adj / used if used else crude

        lo, hi = _wilson(k, len(sub))
        note = ""
        if abs(adj - crude) >= 0.05:
            direction = "worse" if crude > adj else "better"
            note = (f"Crude rate looks {direction} than adjusted. Members on this path were "
                    f"{'sicker' if crude > adj else 'healthier'} to begin with.")
        paths.append(PathResult(label, len(sub), len(sub) / n, round(crude, 3),
                                round(adj, 3),
                                round(float(np.median([r["cost_12mo"] for r in sub])), 0),
                                round(lo, 3), round(hi, 3), note))

    caveats = [
        "Observational, not randomised. Members were not assigned to these paths at random.",
        "Adjusted for severity stratum only. Residual confounding is likely.",
        "Cost is total cost of care in the 12 months after an index visit, not attributable spend.",
        "All data on this page is synthetic.",
    ]
    if any(p.note for p in paths):
        caveats.insert(0, "Crude and adjusted rates disagree for at least one path — read the adjusted column.")

    return PrecedentReport(
        member_id=state.member_id, cohort_size=n,
        confidence="reportable" if n >= 100 else "directional",
        matched_on=["age", "conditions", "eGFR and direction", "prior admissions", "medication count"],
        adjusted_for=["severity stratum (low/moderate/high)"],
        paths=sorted(paths, key=lambda p: -p.n), caveats=caveats)
