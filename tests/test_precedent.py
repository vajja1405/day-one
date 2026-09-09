"""Tests for Precedent. The first two are the ones that matter:
the refusal, and correctly finding the null."""
import numpy as np
import pytest
from precedent.population import generate_population, TRUE_EFFECT
from precedent.index import CohortIndex, MIN_COHORT_SIZE
from precedent.state import build_state
from precedent.outcomes import build_report


@pytest.fixture(scope="module")
def pop():
    states, outcomes = generate_population(4000, seed=7)
    return states, outcomes, CohortIndex(states)


def test_refuses_when_cohort_too_small(pop):
    """The credibility of the whole module. A rare profile must return NO result."""
    _, outcomes, idx = pop
    rare = build_state("RARE", dict(age_band=90, ckd=1, chf=1, copd=1, diabetes=1, afib=1,
                                    med_count=18, egfr=13, egfr_declining=1,
                                    prior_admissions=4, care_gaps=6))
    rep = build_report(rare, idx, outcomes)
    assert rep.confidence == "insufficient"
    assert rep.paths == []
    assert str(MIN_COHORT_SIZE) in rep.reason


def test_caveats_never_empty_on_reportable(pop):
    states, outcomes, idx = pop
    reported = 0
    for s in states[:200]:
        rep = build_report(s, idx, outcomes)
        if rep.confidence != "insufficient":
            reported += 1
            assert rep.caveats, "a reportable result must always carry caveats"
            assert any("Observational" in c for c in rep.caveats)
    assert reported > 0


def test_both_crude_and_adjusted_always_present(pop):
    states, outcomes, idx = pop
    for s in states[:100]:
        rep = build_report(s, idx, outcomes)
        for p in rep.paths:
            assert 0.0 <= p.crude_admission_rate <= 1.0
            assert 0.0 <= p.adjusted_admission_rate <= 1.0


def test_naive_analysis_is_misled_by_confounding(pop):
    """Confirms the trap is really in the data: crude reading calls a protective
    intervention harmful. If this ever fails, the population generator lost its confounding."""
    _, outcomes, _ = pop
    ref = [o for o in outcomes if o["path"] == "nephrology_referral"]
    non = [o for o in outcomes if o["path"] == "no_documented_change"]
    crude_rr = np.mean([o["admitted_12mo"] for o in ref]) / np.mean([o["admitted_12mo"] for o in non])
    assert TRUE_EFFECT["nephrology_referral"] < 1.0      # truly protective
    assert crude_rr > 1.0                                 # but crude says harmful


def test_matched_cohorts_recover_the_null(pop):
    """The hardest test: a path with NO real effect must not be reported as effective."""
    states, outcomes, idx = pop
    rng = np.random.default_rng(3)
    ests = []
    for i in rng.choice(len(states), 250, replace=False):
        ids, _ = idx.query(states[i])
        if len(ids) < MIN_COHORT_SIZE:
            continue
        rows = [outcomes[j] for j in ids]
        a = [r for r in rows if r["path"] == "care_management"]
        b = [r for r in rows if r["path"] == "no_documented_change"]
        if len(a) < 10 or len(b) < 10:
            continue
        rb = np.mean([r["admitted_12mo"] for r in b])
        if rb > 0:
            ests.append(np.mean([r["admitted_12mo"] for r in a]) / rb)
    assert len(ests) > 30
    assert 0.85 <= float(np.median(ests)) <= 1.15, "null effect must be recovered as ~1.0"
