# Shatter findings

This is a controlled degradation experiment over 12 invented members, 11 severity levels, and 20 deterministic seeds per level. Each run starts from a clean fixture, applies the requested Shatter modes, and then calls the real Day One pipeline. A pipeline exception is counted as an error; it is never dropped from the denominator. The results describe this implementation's failure surface, not clinical performance.

## The curve

At severity `0.0`, the pipeline stays at its clean baseline: 100% contradiction detection, 100% abstention on unsupported labels, 100% citation integrity, and no mutation events. When all modes are available together, severity `0.6` produces a 60.00% pipeline-error rate, 35.42% abstention on unsupported labels, 7.78% false findings, 7.27% contradiction detection, and 14.69 mean mutation events per run. At severity `1.0`, every run fails strict ingestion because the fragment contains several incompatible mutations at once. This is useful as a boundary test: the current consumer has no partial-ingestion recovery path.

The curve does not say that records in the world become “60% wrong.” It says that a randomly seeded combination of the declared fault models at that severity exceeds the current ingestion contract that often.

## Mode-isolated ranking at severity 0.6

| Mode | Damage score | Pipeline errors | False findings | Contradiction detection | Citation integrity |
|---|---:|---:|---:|---:|---:|
| Negation loss | 0.74 | 0.00 | 10.69% | 37.05% | 100% |
| Stale-active conflict | 0.63 | 0.00 | 0.00% | 37.27% | 100% |
| Coding drift | 0.35 | 15.83% | 0.00% | 91.36% | 100% |
| Family vs personal history | 0.31 | 0.00% | 10.28% | 100% | 100% |
| Superseded labs | 0.12 | 0.00% | 0.00% | 87.73% | 100% |
| Temporal gaps | 0.06 | 0.00% | 0.00% | 94.32% | 100% |
| Identity drift | 0.00 | 0.00% | 0.00% | 100% | 100% |
| Duplicate encounters | 0.00 | 0.00% | 0.00% | 100% | 100% |
| Medication divergence | 0.00 | 0.00% | 0.00% | 100% | 100% |
| Missing linkage | 0.00 | 0.00% | 0.00% | 100% | 100% |

The score is a transparent harness ranking that weights contradiction misses, false findings, ingestion errors, and unsupported-case abstention. It is not a clinical severity scale. Identity accuracy is measured separately: the identity-drift mode falls to 2.08% exact agreement in its isolated runs, while the other modes leave the identity fields untouched.

## What the worst case looks like

The walkthrough is `SYN-007`, seed `7`, severity `0.6`, with `negation_loss` selected. Two exact mutations remove negation phrases from source excerpts. Day One still preserves the source document IDs and returns a valid pipeline response, but the prediction changes from `contradicted` to `insufficient_evidence` for one condition and to `suggest_confirm` for another. The report stores the original and corrupted hashes plus a reversible patch; `restore()` verifies the clean record before returning it.

That failure is the clearest design lesson. Citation integrity can remain perfect while meaning changes inside a cited excerpt. A citation check proves that a source was linked; it does not prove that a negation or resolution qualifier survived extraction.

## What I would fix first

1. Preserve negation and resolution as typed source spans, with an invariant that makes removal visible to the consumer and the audit.
2. Add a held-out adjudication set authored by clinicians who did not write the fixtures or modes.
3. Add a tolerant quarantine path for code drift and other invalid fragments, so one malformed item does not erase the rest of a member's evidence.
4. Add an identity resolver with explicit organization-local provenance and a fail-closed ambiguity state.

The next experiment should repeat the sweep after those changes and require the same report to restore every fragment byte-for-byte.
