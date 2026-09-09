"""Ten pure transformations over an ingestion-view dictionary.

Selection probability is severity for EACH eligible opportunity. Stable hash
thresholds couple runs across severity, seed, member, mode and opportunity.
These are declared fault models, not estimates of a payer's error distribution.
The _shatter context holds synthetic organization/linkage/fill metadata; Day One
has no consumers for these fields. No clinical pipeline code is altered here.
"""
from copy import deepcopy
from datetime import date, timedelta
import hashlib
import re
from .schemas import MutationEvent

def as_of(record):
    """Use the consumer snapshot date when present; fixtures may only have bundle dates."""
    if record.get('as_of'):
        return date.fromisoformat(record['as_of'])
    dates=[date.fromisoformat(d['date']) for d in record.get('source_documents',[]) if d.get('date')]
    return max(dates) if dates else date(2026,9,6)

MODES = {
    'identity_drift': 'Identity drift',
    'duplicate_encounters': 'Duplicate encounters',
    'stale_active_conflict': 'Stale-active conflict',
    'superseded_labs': 'Superseded labs',
    'medication_divergence': 'Medication divergence',
    'missing_linkage': 'Missing linkage',
    'coding_drift': 'Coding drift',
    'temporal_gap': 'Temporal gaps',
    'family_vs_personal': 'Family vs personal history',
    'negation_loss': 'Negation loss',
}


def draw(record, mode, seed, target):
    text=f"{seed}|{record['member_id']}|{mode}|{target}"
    return int.from_bytes(hashlib.sha256(text.encode()).digest()[:8], 'big') / 2**64


def selected(record, mode, seed, target, severity):
    return severity > 0 and draw(record, mode, seed, target) < severity


def event(mode, target, description, before=None, after=None, source=None, spans=False):
    return MutationEvent(mode=mode,target=target,description=description,
        original_span=before if spans else None,corrupted_span=after if spans else None,
        original_value=before,corrupted_value=after,original_source_doc_id=source)


def drop_documents(r, ids):
    r['source_documents']=[d for d in r['source_documents'] if d['doc_id'] not in ids]
    for field in ('encounters','observations','medications','coded_conditions'):
        r[field]=[x for x in r[field] if x['source_doc_id'] not in ids]


def identity_drift(record, severity, seed):
    """Drift each organization-local identity; no fictional resolver is installed."""
    mode='identity_drift';r=deepcopy(record);events=[]
    profiles=r.get('_shatter',{}).get('source_profiles',[])
    for p in profiles:
        if selected(record,mode,seed,p['organization'],severity):
            before=deepcopy(p)
            p['local_member_id']+='-old'
            p['display_name']=p['display_name'].replace('Synthetic Member','S. Member')
            p['date_of_birth']=(date.fromisoformat(p['date_of_birth'])+timedelta(days=1)).isoformat()
            p['address']='999 Previous Example Road, Example City'
            events.append(event(mode,p['organization'],'Source-local identity no longer exactly matches its peers',before,p))
    return r,events,len(profiles)


def duplicate_encounters(record,severity,seed):
    """Second-source copies have distinct IDs and a one-day reporting difference."""
    mode='duplicate_encounters';r=deepcopy(record);events=[];docs={d['doc_id']:d for d in record['source_documents']}
    for encounter in record['encounters']:
        if selected(record,mode,seed,encounter['encounter_id'],severity):
            d=deepcopy(docs[encounter['source_doc_id']]);e=deepcopy(encounter)
            day=min(date.fromisoformat(d['date'])+timedelta(days=1),as_of(record)).isoformat()
            d.update(doc_id=d['doc_id']+'-duplicate',date=day)
            e.update(encounter_id=e['encounter_id']+'-duplicate',source_doc_id=d['doc_id'],date=day,encounter_type=e['encounter_type']+' / second-source billing report')
            r['source_documents'].append(d);r['encounters'].append(e)
            ctx=r.setdefault('_shatter',{});ctx.setdefault('doc_origins',{})[d['doc_id']]=encounter['source_doc_id']
            ctx.setdefault('encounter_aliases',{})[e['encounter_id']]=encounter['encounter_id']
            ctx.setdefault('encounter_codes',{})[e['encounter_id']]='LOCAL-FOLLOWUP'
            events.append(event(mode,e['encounter_id'],'One visit becomes two source-local encounters; date and billing label drift',encounter,e,encounter['source_doc_id']))
    return r,events,len(record['encounters'])


def stale_active_conflict(record,severity,seed):
    """Copy resolved/ruled-out history into exactly one stale source's active list.

    Original contrary evidence remains visible in the other source. This models
    erroneous source state, not new disease or a physician diagnosing the member.
    """
    mode='stale_active_conflict';r=deepcopy(record);events=[]
    ctx=record.get('_shatter',{});targets=ctx.get('resolved_conditions',{})
    for key,info in targets.items():
        if selected(record,mode,seed,key,severity):
            d_id=f"{record['member_id']}-stale-active-{key}";day=as_of(record).isoformat()
            text=f"SYNTHETIC. Current chart already lists {info['display'].lower()} ({info['code']}); active in ORG-STALE despite a contrary report elsewhere."
            r['source_documents'].append({'doc_id':d_id,'doc_type':'claim','date':day,'excerpt':text})
            r['coded_conditions'].append({'condition_key':key,'code':info['code'],'display':info['display'],'date':day,'source_doc_id':d_id})
            r.setdefault('_shatter',{}).setdefault('doc_origins',{})[d_id]=info['source_doc_id']
            events.append(event(mode,d_id,'Exactly one source carries the ruled-out/resolved history as active',info['original_text'],text,info['source_doc_id'],True))
    return r,events,len(targets)


def superseded_labs(record,severity,seed):
    """Withhold a later normal result and its linked interpretation, retaining the abnormal."""
    mode='superseded_labs';r=deepcopy(record);events=[];targets=[]
    observations=record['observations']
    for obs in observations:
        normal=(obs.get('reference_low') is None or obs['value']>=obs['reference_low']) and (obs.get('reference_high') is None or obs['value']<=obs['reference_high'])
        earlier=[o for o in observations if o['loinc']==obs['loinc'] and o['date']<obs['date'] and ((o.get('reference_low') is not None and o['value']<o['reference_low']) or (o.get('reference_high') is not None and o['value']>o['reference_high']))]
        if normal and earlier:targets.append(obs)
    for obs in targets:
        if selected(record,mode,seed,obs['observation_id'],severity):
            linked=record.get('_shatter',{}).get('lab_interpretations',{}).get(obs['source_doc_id'])
            ids={obs['source_doc_id']}|({linked} if linked else set())
            originals=[d for d in record['source_documents'] if d['doc_id'] in ids]
            drop_documents(r,ids)
            events.append(event(mode,obs['observation_id'],'Later normal lab and linked interpretation do not propagate',originals,None,obs['source_doc_id']))
    return r,events,len(targets)


def medication_divergence(record,severity,seed):
    """Flip chart status while leaving a contradictory synthetic pharmacy fill visible."""
    mode='medication_divergence';r=deepcopy(record);events=[]
    for index,med in enumerate(r['medications']):
        if selected(record,mode,seed,str(index),severity):
            before=deepcopy(med);med['status']='discontinued' if med['status']=='active' else 'active'
            events.append(event(mode,med['name'],'Chart status diverges from the untouched pharmacy-fill context',before,med,med['source_doc_id']))
    return r,events,len(record['medications'])


def missing_linkage(record,severity,seed):
    """Keep the specialist encounter but remove its explicit referral edge."""
    mode='missing_linkage';r=deepcopy(record);events=[]
    referrals=record.get('_shatter',{}).get('referrals',[])
    kept=[]
    for referral in referrals:
        if selected(record,mode,seed,referral['to_encounter'],severity):
            events.append(event(mode,referral['to_encounter'],'Specialist encounter survives without its referral edge',referral,None))
        else:kept.append(referral)
    if events:r['_shatter']['referrals']=kept
    return r,events,len(referrals)


def coding_drift(record,severity,seed):
    """Replace standard codes with local/legacy alternatives WITHOUT repairing Day One's validator."""
    mode='coding_drift';r=deepcopy(record);events=[]
    docs={d['doc_id']:d for d in r['source_documents']}
    for i,condition in enumerate(r['coded_conditions']):
        if selected(record,mode,seed,str(i),severity):
            before=deepcopy(condition);condition['code']=('LOCAL:' if i%2==0 else 'LEGACY:')+condition['code']
            source=docs[condition['source_doc_id']];source['excerpt']=source['excerpt'].replace(before['code'],condition['code'])
            events.append(event(mode,condition['source_doc_id'],'Source uses an unmapped local/legacy code; strict ingestion may reject it',before,condition,condition['source_doc_id']))
    return r,events,len(record['coded_conditions'])


def temporal_gap(record,severity,seed):
    """Lose one 12–24 month coverage window, retaining the enrollment intake document.

    The sampled gap ends 1–6 months before review. Severity controls whether the
    outage occurs, not an asserted relationship to real-world missingness rates.
    """
    mode='temporal_gap';r=deepcopy(record);events=[]
    if selected(record,mode,seed,'coverage-window',severity):
        u=draw(record,mode,seed,'window-duration');months=12+int(u*13)
        lag=1+int(draw(record,mode,seed,'window-lag')*6)
        end=as_of(record)-timedelta(days=lag*30)
        start=end-timedelta(days=months*30)
        ids={d['doc_id'] for d in record['source_documents'] if start.isoformat()<=d['date']<=end.isoformat() and not d['doc_id'].endswith('-intake')}
        if ids:
            before=[d for d in record['source_documents'] if d['doc_id'] in ids]
            drop_documents(r,ids)
            events.append(event(mode,'coverage-window',f'{months}-month observation gap: {start} through {end}',before,{'start':str(start),'end':str(end),'months':months}))
    return r,events,1 if len(record['source_documents'])>1 else 0


def family_vs_personal(record,severity,seed):
    """Drop the exact family-history qualifier from an existing source extraction."""
    mode='family_vs_personal';r=deepcopy(record);events=[];eligible=0
    for d in r['source_documents']:
        if re.search(r'family history of\s+',d['excerpt'],re.I):
            eligible+=1
            if selected(record,mode,seed,d['doc_id'],severity):
                before=d['excerpt'];d['excerpt']=re.sub(r'family history of\s+','',before,flags=re.I)
                events.append(event(mode,d['doc_id'],'Family qualifier lost; an inherited risk becomes apparent personal history',before,d['excerpt'],d['doc_id'],True))
    return r,events,eligible


def negation_loss(record,severity,seed):
    """Remove only explicit negation phrases; do not inject an affirmative template."""
    mode='negation_loss';r=deepcopy(record);events=[];eligible=0
    pattern=r'\bno evidence of\s+|\bruled out\b'
    for d in r['source_documents']:
        if d['doc_type'] in {'encounter_note','discharge_summary'} and re.search(pattern,d['excerpt'],re.I):
            eligible+=1
            if selected(record,mode,seed,d['doc_id'],severity):
                before=d['excerpt'];d['excerpt']=re.sub(pattern,'',before,flags=re.I)
                events.append(event(mode,d['doc_id'],'Negation span lost in the ingestion view; immutable original is kept by the report',before,d['excerpt'],d['doc_id'],True))
    return r,events,eligible

FUNCTIONS={key:globals()[key] for key in MODES}
