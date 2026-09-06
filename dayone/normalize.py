"""Normalize typed FHIR-ish fixtures, deduplicate and sort all records.

Completeness is a transparent availability heuristic, not a probability:
0.25*encounter_present + 0.25*lab_present + 0.20*med_list_present +
0.15*longitudinal_encounters_at_least_90_days + 0.15*any_record_within_365_days.
It measures presence, not truth, clinical adequacy or external network coverage.
"""

from datetime import date
from pathlib import Path

from .schemas import CaseObject, SyntheticBundle

AS_OF = date(2026, 9, 6)


def normalize(bundle: SyntheticBundle | dict | Path, as_of: date = AS_OF) -> CaseObject:
    if isinstance(bundle, Path):
        bundle = SyntheticBundle.model_validate_json(bundle.read_text())
    elif isinstance(bundle, dict):
        bundle = SyntheticBundle.model_validate(bundle)
    else:
        # Revalidate nested lists too; model assignment validation cannot see list mutation.
        bundle = SyntheticBundle.model_validate(bundle.model_dump())

    def unique(items, key):
        by_id = {}
        for item in items:
            identity = key(item)
            if identity in by_id and item != by_id[identity]:
                raise ValueError(f"Conflicting duplicate record: {identity}")
            if item.date > as_of:
                raise ValueError("Future-dated records cannot enter this as-of snapshot")
            by_id[identity] = item
        return sorted(by_id.values(), key=lambda item: (item.date, str(key(item))))

    docs = unique(bundle.source_documents, lambda d: d.doc_id)
    encounters = unique(bundle.encounters, lambda e: e.encounter_id)
    observations = unique(bundle.observations, lambda o: o.observation_id)
    medications = unique(bundle.medications, lambda m: (m.name.lower(), m.date, m.status))
    coded = unique(bundle.coded_conditions, lambda c: (c.condition_key, c.date))
    components = {
        "encounters": 0.25 * bool(encounters), "labs": 0.25 * bool(observations),
        "med_list": 0.20 * any(d.doc_type == "med_list" for d in docs),
        "longitudinal": 0.15 * bool(encounters and (encounters[-1].date - encounters[0].date).days >= 90),
        "recency": 0.15 * any((as_of - d.date).days <= 365 for d in docs),
    }
    return CaseObject(member_id=bundle.member_id, demographics=bundle.demographics, scenario=bundle.meta.scenario, as_of=as_of,
                      coded_conditions=coded, medications=medications, encounters=encounters, observations=observations,
                      source_documents=docs, record_completeness=round(sum(components.values()), 2), completeness_components=components)
