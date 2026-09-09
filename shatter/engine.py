"""Seeded mode composition and exact reconstruction, independent of the system scored."""
from copy import deepcopy
import math
from .modes import FUNCTIONS
from .schemas import FragmentationReport,Patch,digest


def shatter(record, severity: float, modes: list[str] | None = None, seed: int = 0):
    """Return (ingestion-view dict, report). Input may be a CaseObject or JSON dict.

    Deliberate corruption can violate the consumer's schema, so output is a raw
    dictionary, never model_construct() or a falsely validated CaseObject.
    Unknown modes/duplicates and nonfinite/out-of-range severities are rejected.
    Empty modes means no corruption; None enables the ten modes in declared order.
    """
    if isinstance(severity,bool) or not isinstance(severity,(float,int)) or not math.isfinite(severity) or not 0<=severity<=1:
        raise ValueError('severity must be finite, from 0 to 1')
    if isinstance(seed,bool) or not isinstance(seed,int):raise ValueError('seed must be an integer')
    modes=list(FUNCTIONS) if modes is None else list(modes)
    if len(set(modes))!=len(modes) or any(m not in FUNCTIONS for m in modes):raise ValueError('Unknown or duplicate modes')
    raw=record.model_dump(mode='json') if hasattr(record,'model_dump') else deepcopy(record)
    if not isinstance(raw,dict): raise ValueError('A record dictionary or CaseObject is required')
    # CaseObject carries `synthetic=True`; the source bundle carries the same
    # fact as meta.label. Accept either, but never infer synthetic status from
    # a member id or a caller-supplied flag alone.
    if not (raw.get('synthetic') is True or raw.get('meta',{}).get('label') == 'SYNTHETIC'):
        raise ValueError('Only explicitly synthetic records are accepted')
    original_context=deepcopy(raw.get('_shatter',{}))
    current=deepcopy(raw);patches=[];events=[];eligible={};fired={}
    for mode in modes:
        after,changes,count=FUNCTIONS[mode](current,severity,seed)
        eligible[mode]=count;fired[mode]=len(changes)
        for field in sorted((set(current)|set(after)) - {'_shatter'}):
            if current.get(field)!=after.get(field):
                patches.append(Patch(mode=mode,field=field,existed_before=field in current,before=deepcopy(current.get(field)),after=deepcopy(after.get(field))))
        current=after;events.extend(changes)
    # `_shatter` is generator-side ground truth and linkage metadata. It is
    # removed before the consumer sees the corrupted record so the pipeline
    # cannot accidentally use answer labels or repair hints.
    public_original=deepcopy(raw);public_original.pop('_shatter',None)
    public_fragmented=deepcopy(current);public_fragmented.pop('_shatter',None)
    report=FragmentationReport(member_id=raw['member_id'],severity=severity,seed=seed,requested_modes=modes,
        original_sha256=digest(public_original),fragmented_sha256=digest(public_fragmented),patches=patches,events=events,
        eligibility=eligible,fired=fired,ground_truth=deepcopy(raw.get('_shatter',{}).get('ground_truth',{})))
    return public_fragmented,report
