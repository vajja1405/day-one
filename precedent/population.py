"""Synthetic population with KNOWN ground truth — including a deliberately confounded path.

The point of this module is to build a population where the naive reading of the data gives
the WRONG answer, so the analysis can be tested against something I control.

Ground truth, by construction:
  nephrology_referral   genuinely REDUCES admissions (true relative effect ~0.75)
                        BUT is given far more often to sicker members, so the CRUDE rate
                        makes it look HARMFUL. This is the confounding trap.
  medication_adjustment mildly helpful (~0.92)
  no_documented_change  baseline
  care_management       NO real effect (~1.00) — the analysis must find nothing here
"""
from __future__ import annotations
import numpy as np
from .state import build_state, MemberState

PATHS = ["nephrology_referral", "medication_adjustment", "care_management", "no_documented_change"]

TRUE_EFFECT = {           # multiplier on baseline admission risk
    "nephrology_referral": 0.75,
    "medication_adjustment": 0.92,
    "care_management": 1.00,     # the null — must NOT be reported as effective
    "no_documented_change": 1.00,
}


def generate_population(n: int = 4000, seed: int = 7) -> tuple[list[MemberState], list[dict]]:
    rng = np.random.default_rng(seed)
    states, outcomes = [], []

    for i in range(n):
        age = int(rng.integers(65, 91))
        ckd = float(rng.random() < 0.34)
        chf = float(rng.random() < 0.22)
        copd = float(rng.random() < 0.18)
        dm = float(rng.random() < 0.38)
        afib = float(rng.random() < 0.14)
        egfr = float(np.clip(rng.normal(72 - 22 * ckd - 6 * chf, 14), 12, 110))
        declining = float(rng.random() < (0.5 if ckd else 0.18))
        prior_adm = int(rng.poisson(0.35 + 0.9 * chf + 0.4 * copd))
        meds = int(np.clip(rng.normal(5 + 3 * ckd + 3 * chf + 2 * dm, 2), 0, 18))
        gaps = int(np.clip(rng.poisson(1.6), 0, 6))

        raw = dict(age_band=age, ckd=ckd, chf=chf, copd=copd, diabetes=dm, afib=afib,
                   med_count=meds, egfr=egfr, egfr_declining=declining,
                   prior_admissions=prior_adm, care_gaps=gaps)
        st = build_state(f"POP-{i:05d}", raw)

        # --- THE CONFOUNDING, built in on purpose -------------------------------------
        # Sicker members are much more likely to be referred. So any crude comparison of
        # referred vs not-referred is comparing sicker people to healthier people.
        p_ref = 0.06 + 0.62 * st.severity
        p_med = 0.34 - 0.10 * st.severity
        p_cm  = 0.18
        p_non = max(0.02, 1.0 - p_ref - p_med - p_cm)
        probs = np.array([p_ref, p_med, p_cm, p_non]); probs = probs / probs.sum()
        path = PATHS[int(rng.choice(len(PATHS), p=probs))]

        # Baseline risk depends on severity; the path then multiplies it by its TRUE effect.
        baseline = 0.06 + 0.55 * st.severity
        risk = float(np.clip(baseline * TRUE_EFFECT[path], 0.01, 0.95))
        admitted = bool(rng.random() < risk)

        cost = float(max(2200, rng.normal(
            9000 + 34000 * st.severity + (17000 if admitted else 0), 4200)))

        states.append(st)
        outcomes.append(dict(member_id=st.member_id, path=path, admitted_12mo=admitted,
                             cost_12mo=cost, severity=st.severity,
                             severity_stratum=st.severity_stratum))
    return states, outcomes
