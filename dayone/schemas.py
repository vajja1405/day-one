"""Pydantic contracts. Confidence is an uncalibrated status-confidence heuristic."""

from datetime import date, datetime
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Status = Literal["suggest_confirm", "insufficient_evidence", "contradicted", "already_documented"]
Action = Literal["flag_for_physician_confirmation", "no_action", "request_records", "already_on_chart"]
ConditionKey = Literal["ckd", "chf", "copd", "diabetes", "af", "depression"]
CODED_IDENTITIES = {"ckd": ("N18.9", "Chronic kidney disease"), "chf": ("I50.9", "Heart failure"), "copd": ("J44.9", "COPD"),
                    "diabetes": ("E11.9", "Type 2 diabetes"), "af": ("I48.91", "Atrial fibrillation"), "depression": ("F32.A", "Depression")}


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class Demographics(Contract):
    age_band: str
    sex: Literal["female", "male", "unspecified"]


class SourceDoc(Contract):
    doc_id: str
    doc_type: Literal["encounter_note", "lab_result", "med_list", "discharge_summary", "claim"]
    date: date
    excerpt: str = Field(min_length=1)


class CodedCondition(Contract):
    condition_key: ConditionKey
    code: str
    display: str
    date: date
    source_doc_id: str

    @model_validator(mode="after")
    def code_identity(self):
        if (self.code, self.display.lower()) != (CODED_IDENTITIES[self.condition_key][0], CODED_IDENTITIES[self.condition_key][1].lower()):
            raise ValueError("Condition key, code and display must match the fixture vocabulary")
        return self


class Medication(Contract):
    name: str
    status: Literal["active", "discontinued"]
    date: date
    source_doc_id: str


class Encounter(Contract):
    encounter_id: str
    date: date
    encounter_type: str
    source_doc_id: str


class Observation(Contract):
    observation_id: str
    name: str
    loinc: str
    value: float
    unit: str
    date: date
    reference_low: float | None = None
    reference_high: float | None = None
    condition_key: ConditionKey | None = None
    source_doc_id: str


class BundleMeta(Contract):
    label: Literal["SYNTHETIC"] = "SYNTHETIC"
    scenario: Literal["rich", "sparse", "contradictory", "stale", "already_documented"]
    generated_for: str = "Independent Day One demonstration; no real person"


class SyntheticBundle(Contract):
    """FHIR-ish fixture, intentionally not a conformant FHIR R4 interchange bundle."""
    resourceType: Literal["Bundle"] = "Bundle"
    type: Literal["collection"] = "collection"
    member_id: str = Field(pattern=r"^SYN-\d{3}$")
    meta: BundleMeta
    demographics: Demographics
    coded_conditions: list[CodedCondition] = Field(default_factory=list)
    medications: list[Medication] = Field(default_factory=list)
    encounters: list[Encounter] = Field(default_factory=list)
    observations: list[Observation] = Field(default_factory=list)
    source_documents: list[SourceDoc] = Field(min_length=1)

    @model_validator(mode="after")
    def source_integrity(self):
        docs = {d.doc_id: d for d in self.source_documents}
        for collection in (self.coded_conditions, self.medications, self.encounters, self.observations):
            for item in collection:
                if item.source_doc_id not in docs:
                    raise ValueError(f"Unknown source document: {item.source_doc_id}")
                source = docs[item.source_doc_id]
                if item.date != source.date:
                    raise ValueError(f"Structured record date differs from source date: {item.source_doc_id}")
                if isinstance(item, Observation):
                    if item.name.lower() not in source.excerpt.lower() or item.loinc not in source.excerpt or f"{item.value:g} {item.unit}" not in source.excerpt:
                        raise ValueError(f"Structured observation not substantiated by source: {item.source_doc_id}")
                if isinstance(item, CodedCondition):
                    if item.code not in source.excerpt or item.display.lower() not in source.excerpt.lower():
                        raise ValueError(f"Structured chart condition not substantiated by source: {item.source_doc_id}")
                if isinstance(item, Medication) and item.name.lower() not in source.excerpt.lower():
                    raise ValueError(f"Structured medication not substantiated by source: {item.source_doc_id}")
        return self


class CaseObject(Contract):
    member_id: str
    demographics: Demographics
    scenario: str
    synthetic: Literal[True] = True
    as_of: date
    coded_conditions: list[CodedCondition]
    medications: list[Medication]
    encounters: list[Encounter]
    observations: list[Observation]
    record_completeness: float = Field(ge=0, le=1)
    completeness_components: dict[str, float]
    source_documents: list[SourceDoc]


class Evidence(Contract):
    source_doc_id: str
    date: date
    detail: str = Field(min_length=1)
    recency_days: int = Field(ge=0)


class KnowledgeSnippet(Contract):
    snippet_id: str
    condition_key: ConditionKey
    title: str
    text: str
    source_url: str
    reviewed_at: date


class Candidate(Contract):
    finding_id: str
    condition_key: ConditionKey
    label: str
    derivation: list[str]
    evidence_for: list[Evidence] = Field(default_factory=list)
    evidence_against: list[Evidence] = Field(default_factory=list)
    context_evidence: list[Evidence] = Field(default_factory=list)
    knowledge: list[KnowledgeSnippet] = Field(default_factory=list)
    status_hint: Status | None = None
    support_adequate: bool = False
    retrieval_method: str = "keyword"


class Finding(Contract):
    finding_id: str
    condition_key: ConditionKey
    label: str
    status: Status
    confidence: float = Field(ge=0, le=1)
    evidence_for: list[Evidence]
    evidence_against: list[Evidence]
    context_evidence: list[Evidence] = Field(default_factory=list)
    reasoning: str = Field(max_length=900)
    recommended_action: Action
    automation_level: Literal["recommend_only", "reversible_action", "requires_human"]
    human_review_required: bool
    derivation: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)
    knowledge_references: list[KnowledgeSnippet] = Field(default_factory=list)

    @model_validator(mode="after")
    def evidence_safety_contract(self):
        if self.status == "suggest_confirm" and not self.evidence_for:
            raise ValueError("suggest_confirm requires supporting evidence")
        if self.status == "insufficient_evidence" and self.evidence_for:
            raise ValueError("insufficient_evidence must have empty evidence_for")
        if self.confidence < 0.5 and self.recommended_action == "flag_for_physician_confirmation":
            raise ValueError("Low-confidence finding cannot flag physician confirmation")
        sentences = [s for s in re.split(r"[.!?](?:\s|$)", self.reasoning.strip()) if s.strip()]
        if len(sentences) > 2:
            raise ValueError("Reasoning must be at most two sentences")
        citations = self.evidence_for + self.evidence_against + self.context_evidence
        if citations and not any(e.source_doc_id in self.reasoning for e in citations):
            raise ValueError("Reasoning must reference a supplied source document id")
        return self


class CareGap(Contract):
    gap_id: str
    label: str
    reason: str
    recommended_action: Literal["review_records_with_physician", "request_records"]
    evidence: list[Evidence] = Field(default_factory=list)
    reviewed_source_doc_ids: list[str]


class MedicationFlag(Contract):
    flag_id: str
    label: str
    reason: str
    recommended_action: Literal["reconcile_with_physician"] = "reconcile_with_physician"
    evidence: list[Evidence]


class DayOneBrief(Contract):
    member_id: str
    generated_at: datetime
    as_of: date
    synthetic: Literal[True] = True
    record_completeness: float = Field(ge=0, le=1)
    confidence_note: str = "Uncalibrated heuristic confidence in the record status, not disease probability."
    findings: list[Finding]
    care_gaps: list[CareGap]
    medication_flags: list[MedicationFlag]
    unknowns: list[str]
    audit_id: str


class ReasoningResult(Contract):
    findings: list[Finding]
    llm_called: bool = False
    model: str | None = None
    prompt_hash: str | None = None
    validation_retries: int = 0
    fallbacks: list[str] = Field(default_factory=list)
    usage: dict[str, int] = Field(default_factory=dict)


class DeterministicResult(Contract):
    candidates: list[Candidate]
    care_gaps: list[CareGap]
    medication_flags: list[MedicationFlag]
    unknowns: list[str]
    rules_fired: list[str]


class AuditRecord(Contract):
    model_config = ConfigDict(extra="forbid", frozen=True)
    audit_id: str
    timestamp: datetime
    as_of: date
    member_id: str
    synthetic: Literal[True] = True
    source_documents: list[dict]
    knowledge_base_version: str
    knowledge_base_sha256: str
    deterministic_rules_fired: list[str]
    llm: dict
    candidate_outcomes: list[dict]
    authorization: list[dict]
    fallbacks: list[str]
    brief_sha256: str
    previous_record_sha256: str | None
    record_sha256: str = ""
