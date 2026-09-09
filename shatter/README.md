# Shatter

Shatter is a small, deterministic fragmentation layer for synthetic clinical-record ingestion tests. It keeps a clean record as the source of truth, applies one or more declared failure modes at a severity from `0.0` to `1.0`, and returns a mutated ingestion view plus a hash-checked `FragmentationReport`.

It is deliberately independent of Day One's clinical logic. The report records the exact mutation, original and corrupted values or text spans, source document IDs, eligibility counts, and a reversible patch history. Private `_shatter` fixture context is stripped before the consumer sees the record.

```python
from shatter import shatter

fragmented, report = shatter(bundle, severity=0.6, seed=7)
original = report.restore(fragmented)
```

The ten modes are identity drift, duplicate encounters, stale-active conflict, superseded labs, medication divergence, missing linkage, coding drift, temporal gaps, family-versus-personal history, and negation loss. They are fault models for a controlled harness, not claims about frequency or severity in a payer's data.

Shatter is MIT licensed. Use it, fork it, replace its modes, or adapt the report schema for another synthetic-record consumer.
