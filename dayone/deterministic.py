"""Rules run BEFORE retrieval or a model: auditable, free, fast, repeatable.

Rules cannot invent text; they can still be incomplete or wrong. The model only
receives unresolved cases. This prototype reviews record status, never diagnoses
from a lab, medication, symptom or demographic characteristic.
"""

import re

from .generate import CONDITIONS
from .schemas import Candidate, CareGap, CaseObject, DeterministicResult, Evidence, MedicationFlag, SourceDoc

ALIASES = {
    "ckd": ("chronic kidney disease", "ckd"), "chf": ("heart failure", "chf"),
    "copd": ("copd", "chronic obstructive pulmonary"), "diabetes": ("type 2 diabetes", "diabetes"),
    "af": ("atrial fibrillation",), "depression": ("depression",),
}
NEGATION = ("ruled out", "resolved", "transient", "no evidence of", "normalised", "normalized", "discontinued")


def mentions(text: str, key: str) -> bool:
    return any(re.search(r"\b" + re.escape(alias) + r"\b", text.lower()) for alias in ALIASES[key])


def evidence(doc: SourceDoc, case: CaseObject) -> Evidence:
    return Evidence(source_doc_id=doc.doc_id, date=doc.date, detail=doc.excerpt, recency_days=(case.as_of-doc.date).days)


def classify_doc(doc: SourceDoc, key: str) -> str | None:
    """Conservative phrase matcher; negation scope is confined to a condition sentence.

    Unsupported wording and uncertain statements are contextual only. Reference
    ranges and medications never count as affirmative disease evidence.
    """
    if not mentions(doc.excerpt, key):
        return None
    roles = []
    aliases = "(?:" + "|".join(re.escape(alias) for alias in ALIASES[key]) + ")"
    # Deliberately narrow grammar, with target-specific clauses. Unhandled prose
    # stays context rather than inheriting another condition's documentation.
    for clause in re.split(r"[.!?]\s+|;\s*|\b(?:and|but|however|while)\b", doc.excerpt.lower()):
        if not mentions(clause, key):
            continue
        if doc.doc_type in {"encounter_note", "discharge_summary"}:
            negated = re.search(r"\bno evidence of (?:current )?" + aliases + r"\b", clause) or re.search(aliases + r"\b\s+(?:(?:was|is|has been)\s+)?(?:ruled out|resolved|discontinued)\b", clause)
            if negated:
                roles.append("against")
                continue
            guarded = re.search(r"\b(?:no|not|denies|family|uncertain|possible|suspected|provisional|cannot|without)\b", clause)
            if not guarded and re.search(r"\bclinician documents\s+" + aliases + r"\b", clause):
                roles.append("for")
            elif re.search(r"\bprovisional concern for\s+" + aliases + r"\b", clause):
                roles.append("historical")
    return "against" if "against" in roles else "for" if "for" in roles else "historical" if "historical" in roles else "context"


def run_rules(case: CaseObject, condition_keys: list[str] | None = None) -> DeterministicResult:
    keys = condition_keys or list(CONDITIONS)
    if any(key not in CONDITIONS for key in keys) or len(set(keys)) != len(keys):
        raise ValueError("Condition keys must be unique supported record-review topics")
    documents = {doc.doc_id: doc for doc in case.source_documents}
    candidates, rules, care_gaps, med_flags = [], [], [], []
    for key in keys:
        candidate = Candidate(finding_id=f"{case.member_id}-{key}", condition_key=key,
                              label=f"Review external {CONDITIONS[key][0].lower()} history", derivation=[])
        coded = [c for c in case.coded_conditions if c.condition_key == key]
        if coded:
            candidate.status_hint = "already_documented"
            candidate.evidence_for = [evidence(documents[c.source_doc_id], case) for c in coded]
            candidate.support_adequate = True
            candidate.derivation.append("rule:already_coded")
        else:
            adequate_dates = []
            for doc in case.source_documents:
                role = classify_doc(doc, key)
                if role in {"for", "historical"}:
                    candidate.evidence_for.append(evidence(doc, case))
                    if role == "for" and (case.as_of-doc.date).days <= 365:
                        candidate.support_adequate = True
                        adequate_dates.append(doc.date)
                elif role == "against":
                    candidate.evidence_against.append(evidence(doc, case))
                elif role == "context":
                    candidate.context_evidence.append(evidence(doc, case))
            supports = candidate.evidence_for
            latest_support = max(adequate_dates, default=None)
            latest_against = max((item.date for item in candidate.evidence_against), default=None)
            if latest_against and (latest_support is None or latest_against >= latest_support):
                candidate.status_hint = "contradicted"
                candidate.derivation.append("rule:later_explicit_negation")
            elif candidate.support_adequate:
                candidate.status_hint = "suggest_confirm"
                candidate.derivation.append("rule:recent_explicit_clinician_documentation")
            elif supports:
                candidate.derivation.append("rule:historical_or_provisional_requires_records")
                if all(e.recency_days >= 1460 for e in supports):
                    candidate.derivation.append("rule:stale_evidence")
            else:
                candidate.status_hint = "insufficient_evidence"
                candidate.derivation.append("rule:no_adequate_documentation")
            if supports and all(e.recency_days >= 1460 for e in supports) and "rule:stale_evidence" not in candidate.derivation:
                candidate.derivation.append("rule:stale_evidence")
        rules.extend(candidate.derivation)
        candidates.append(candidate)

    read_ids = list(documents)
    for obs in case.observations:
        outside = ((obs.reference_low is not None and obs.value < obs.reference_low) or
                   (obs.reference_high is not None and obs.value > obs.reference_high))
        if outside:
            age = (case.as_of-obs.date).days
            rules.append("rule:outside_fixture_reference_range")
            care_gaps.append(CareGap(gap_id=f"range-{obs.observation_id}", label=f"Historical result to review: {obs.name}",
                reason=f"{obs.value:g} {obs.unit} on {obs.date.isoformat()} ({age} days old) is outside this fixture's reference interval; review chronology and subsequent records, without inferring a diagnosis.",
                recommended_action="review_records_with_physician", evidence=[evidence(documents[obs.source_doc_id], case)], reviewed_source_doc_ids=read_ids))
    if any(c.condition_key == "diabetes" for c in case.coded_conditions) and not any(o.loinc == "4548-4" and (case.as_of-o.date).days <= 365 for o in case.observations):
        rules.append("rule:diabetes_hba1c_record_missing_12m")
        care_gaps.append(CareGap(gap_id="diabetes-hba1c-record", label="Recent HbA1c record not found", reason="Diabetes is already on the chart but no HbA1c is available in the last 12 months of supplied records; care may have occurred elsewhere.", recommended_action="request_records", reviewed_source_doc_ids=read_ids))
    care_gaps.append(CareGap(gap_id="preventive-history", label="Preventive-care history not supplied", reason="For this Medicare-age intake, ask about vaccination and screening history and obtain prior records; missing documentation does not prove overdue care.", recommended_action="request_records", reviewed_source_doc_ids=read_ids))
    if case.medications:
        med_docs = {m.source_doc_id for m in case.medications}
        stale = all((case.as_of-m.date).days > 365 for m in case.medications)
        med_flags.append(MedicationFlag(flag_id="medication-reconciliation", label="Older medication list needs reconciliation" if stale else "Confirm current medication use",
            reason="External lists do not establish current use, indication or adherence; reconcile names, doses, allergies and discontinued items with the member and clinician.",
            evidence=[evidence(documents[doc_id], case) for doc_id in sorted(med_docs)]))
        rules.append("rule:medication_list_reconciliation")
    unknowns = ["Which outside clinicians hold additional records?", "What matters most to the member at the first visit?", "What are the current medication doses and allergies?", "Were vaccinations or preventive screening completed elsewhere?"]
    if case.record_completeness < 0.6:
        unknowns.insert(0, "The supplied record is sparse; chronic conditions and current therapies remain unverified.")
    return DeterministicResult(candidates=candidates, care_gaps=care_gaps, medication_flags=med_flags, unknowns=unknowns, rules_fired=sorted(set(rules)))
