"""Precompute Precedent data for the site and run the ground-truth validation.

Writes site/public/data/precedent.json — everything the page needs, static, no backend.
"""
from __future__ import annotations
import json, statistics as st
from pathlib import Path
import numpy as np
from .population import generate_population, TRUE_EFFECT, PATHS
from .index import CohortIndex, MIN_COHORT_SIZE
from .state import build_state, STATE_FEATURES
from .outcomes import build_report

POP_N, SEED = 6000, 11
REF = "no_documented_change"


def _rr(rows, path):
    a = [r for r in rows if r["path"] == path]
    b = [r for r in rows if r["path"] == REF]
    if len(a) < 10 or len(b) < 10:
        return None
    rb = float(np.mean([r["admitted_12mo"] for r in b]))
    return float(np.mean([r["admitted_12mo"] for r in a]) / rb) if rb > 0 else None


def build() -> dict:
    states, outcomes = generate_population(POP_N, seed=SEED)
    index = CohortIndex(states)

    # --- validation: naive vs matched, against known truth ---------------------
    naive = {p: _rr(outcomes, p) for p in PATHS if p != REF}
    rng = np.random.default_rng(3)
    pooled = {p: [] for p in naive}
    eligible = 0
    for i in rng.choice(len(states), 400, replace=False):
        ids, _ = index.query(states[i])
        if len(ids) < MIN_COHORT_SIZE:
            continue
        eligible += 1
        rows = [outcomes[j] for j in ids]
        for p in pooled:
            v = _rr(rows, p)
            if v is not None:
                pooled[p].append(v)
    matched = {p: (float(st.median(v)) if v else None) for p, v in pooled.items()}

    validation = []
    for p in naive:
        t = TRUE_EFFECT[p]
        validation.append(dict(
            path=p, true=t,
            naive=round(naive[p], 3) if naive[p] else None,
            matched=round(matched[p], 3) if matched[p] else None,
            naive_error=round(abs(naive[p] - t), 3) if naive[p] else None,
            matched_error=round(abs(matched[p] - t), 3) if matched[p] else None,
            winner=("matched" if abs(matched[p] - t) < abs(naive[p] - t) else "naive")
                   if (naive[p] and matched[p]) else None,
            sign_inverted=bool(naive[p] and t < 0.95 and naive[p] > 1.05),
        ))

    # --- example reports: a reportable one, and a refusal ----------------------
    # Prefer a clinically interesting member who ALSO has a cohort big enough to be
    # convincing: at least three distinct paths, then largest cohort wins.
    cands = []
    for s in states:
        if not (s.raw["ckd"] or s.raw["chf"]):
            continue
        rep = build_report(s, index, outcomes)
        if rep.confidence != "insufficient" and len(rep.paths) >= 3:
            cands.append((len(rep.paths), rep.cohort_size, s, rep))
    cands.sort(key=lambda t: (-t[0], -t[1]))
    examples = [r.to_dict() | {"profile": s.raw, "severity": round(s.severity, 3)}
                for _, _, s, r in cands[:3]]
    rare = build_state("SYN-RARE", dict(age_band=90, ckd=1, chf=1, copd=1, diabetes=1, afib=1,
                                        med_count=18, egfr=13, egfr_declining=1,
                                        prior_admissions=4, care_gaps=6))
    refusal = build_report(rare, index, outcomes).to_dict() | {"profile": rare.raw}

    return dict(
        synthetic=True,
        population_size=POP_N,
        min_cohort_size=MIN_COHORT_SIZE,
        cohorts_reportable=eligible, cohorts_sampled=400,
        features=[{"name": n, "why": w} for n, w in STATE_FEATURES],
        true_effects=TRUE_EFFECT,
        validation=validation,
        examples=examples,
        refusal=refusal,
        limitations=[
            "Entirely synthetic. The confounding structure is one I invented; real confounding is worse and stranger.",
            "Severity is fully observable here by construction. In real data it is partly unobserved, and that is exactly where residual confounding lives.",
            "Matching is not uniformly better. On the weakest true effect it overstates the benefit and does worse than naive comparison.",
            "Cohort sizes here are generous. A real deployment might find common profiles too sparse, which would end the idea.",
            "Observational throughout. Nothing here establishes causation.",
        ],
    )


if __name__ == "__main__":
    data = build()
    out = Path(__file__).resolve().parents[1] / "site" / "public" / "data" / "precedent.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2) + "\n")
    print(f"wrote {out}  ({out.stat().st_size:,} bytes)")
    for v in data["validation"]:
        flag = "  SIGN INVERTED" if v["sign_inverted"] else ""
        print(f"  {v['path']:24s} true={v['true']:.2f} naive={v['naive']:.2f} matched={v['matched']:.2f} -> {v['winner']}{flag}")
