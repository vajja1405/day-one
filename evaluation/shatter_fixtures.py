"""Separate augmented corpus; labels are authored, never copied from model output.

The original 12 Day One files and original 30-case golden set remain unchanged.
Each member receives two narrowly worded probes: family history of an otherwise
unsupported condition and explicit negation of a different unsupported condition.
This intentionally exposes a known extraction pathway, not an independent sample.
"""
from copy import deepcopy
from pathlib import Path
from dayone.normalize import normalize
from dayone.generate import ROOT,CONDITIONS

SUPPORTED={1:['ckd','diabetes','chf'],2:['copd','af','depression'],3:['ckd','diabetes']}
CONTRADICTED={7:['ckd','diabetes','chf'],8:['copd','af','depression'],9:['ckd','diabetes'],10:['chf','depression']}
CHARTED={11:['ckd','diabetes','chf'],12:['copd','af','depression']}


def fixtures():
    records=[]
    for n in range(1,13):
        r=normalize(ROOT/f'data/synthetic/SYN-{n:03d}.json').model_dump(mode='json')
        labels={key:'suggest_confirm' if key in SUPPORTED.get(n,[]) else 'contradicted' if key in CONTRADICTED.get(n,[]) else 'already_documented' if key in CHARTED.get(n,[]) else 'insufficient_evidence' for key in CONDITIONS}
        absent=[key for key in CONDITIONS if labels[key]=='insufficient_evidence']
        family,negative=absent[:2]
        for kind,key,phrase in [('family',family,'family history of'),('negation',negative,'no evidence of')]:
            d_id=f'{r["member_id"]}-shatter-{kind}'
            r['source_documents'].append({'doc_id':d_id,'doc_type':'encounter_note','date':'2026-08-14','excerpt':f'SYNTHETIC. Clinician documents {phrase} {CONDITIONS[key][0].lower()}.'})
            r['encounters'].append({'encounter_id':'E-'+d_id,'date':'2026-08-14','encounter_type':'external specialist review','source_doc_id':d_id})
        labels[negative]='contradicted'
        profiles=[{'organization':f'ORG-{letter}','local_member_id':f'{r["member_id"]}-{letter}', 'display_name':f'Synthetic Member {n:03d}', 'date_of_birth':'1950-05-15','address':'100 Example Way, Example City'} for letter in 'ABCD']
        ctx={'ground_truth':labels,'source_profiles':profiles,'doc_origins':{},'document_organizations':{d['doc_id']:f'ORG-{"ABCD"[i%4]}' for i,d in enumerate(r['source_documents'])},
            'referrals':[{'from_encounter':r['encounters'][-1]['encounter_id'],'to_encounter':e['encounter_id']} for e in r['encounters'] if e['encounter_type']=='external specialist review'],
            'pharmacy_fills':[{'name':m['name'],'last_fill':'2026-08-10','status':m['status']} for m in r['medications']],
            'lab_interpretations':{},'resolved_conditions':{}}
        for key,status in labels.items():
            if status=='contradicted':
                d=next((d for d in r['source_documents'] if d['doc_id']==f'{r["member_id"]}-{key}-review'),None)
                if d is None:d=next(d for d in r['source_documents'] if d['doc_id']==f'{r["member_id"]}-shatter-negation')
                ctx['resolved_conditions'][key]={'code':CONDITIONS[key][1],'display':CONDITIONS[key][0],'source_doc_id':d['doc_id'],'original_text':d['excerpt']}
        for obs in r['observations']:
            if obs['source_doc_id'].endswith('-repeat'):
                ctx['lab_interpretations'][obs['source_doc_id']]=f'{r["member_id"]}-{obs["condition_key"]}-review'
        r['_shatter']=ctx;records.append(r)
    return records


def as_bundle(record):
    """Whitelist Day One's CURRENT interface. No code mapping, identity resolution,
    denoising, source correction or validator bypass is performed by this adapter.
    _shatter is never given to the clinical pipeline (including the answer labels).
    """
    return {'resourceType':'Bundle','type':'collection','member_id':record['member_id'],
        'meta':{'label':'SYNTHETIC','scenario':record['scenario']},'demographics':deepcopy(record['demographics']),
        **{key:deepcopy(record[key]) for key in ['coded_conditions','medications','encounters','observations','source_documents']}}
