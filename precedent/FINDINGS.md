# Precedent — validation findings

Synthetic population, n=6,000, with a **known ground truth effect** built into the generator,
including one care path deliberately confounded (sicker members are far more likely to be
referred) and one path with **no real effect at all**.

The question: does matched-cohort inference recover the truth better than naive comparison?

## Result

True effect is a risk ratio for 12-month admission vs `no_documented_change`.

| Care path | TRUE | Naive population comparison | Matched cohorts (Precedent) |
|---|---|---|---|
| nephrology_referral | **0.75** (protective) | **1.14 — says HARMFUL** ❌ | **0.71** ✓ (error −0.04) |
| care_management | **1.00** (no effect) | **1.24 — says harmful** ❌ | **1.01** ✓ (error +0.01) |
| medication_adjustment | **0.92** (mild benefit) | 1.00 (error +0.08) | 0.77 (error −0.15) ❌ |

364 of 400 sampled members had a cohort large enough to report; the other 36 correctly
returned no result.

## What this shows

**Naive analysis inverts the sign on the most important path.** A genuinely protective
intervention (0.75) reads as harmful (1.14), because sicker members are referred more often.
Anyone eyeballing the crude numbers would conclude referral hurts patients. It doesn't.

**Matched cohorts recover it** (0.71 vs 0.75 true) and, more importantly, **correctly find the
null** on `care_management` (1.01 vs 1.00 true). A system that can correctly say *"this
intervention does nothing"* is rarer than one that finds effects.

## What this does NOT show — the honest half

**On `medication_adjustment` the matched approach is worse than naive** (error −0.15 vs +0.08).
It overstates the benefit of the weakest real effect. I have not fully diagnosed why; the most
likely explanation is that tight matching shrinks within-cohort severity variation, so the
remaining contrast on a small effect is dominated by noise, and the median across cohorts is
biased by the cohorts where the comparison arm happened to do badly.

That is a real limitation and it belongs on the page, not in a footnote. The method is clearly
better where confounding is strong and no better — possibly worse — where the effect is weak.

## Other limitations

- Entirely synthetic. The confounding structure is one I invented; real confounding is worse
  and stranger.
- Severity is observable here by construction. In real data it is partly unobserved, which is
  exactly where residual confounding lives.
- Cohort sizes here are generous. A real deployment might find common profiles too sparse,
  which would kill the product. **That is the first thing I would test against real data,
  before building anything.**
