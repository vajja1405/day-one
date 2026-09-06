from collections import Counter
from datetime import date
import pytest

from dayone.deterministic import classify_doc, run_rules
from dayone.generate import generate, make_bundle
from dayone.normalize import AS_OF, normalize
from dayone.pipeline import run_pipeline
from dayone.retrieve import retrieve
from dayone.schemas import SourceDoc, SyntheticBundle


def test_all_synthetic_bundles_validate(tmp_path):
    bundles = generate(tmp_path)
    assert len(bundles) == 12
    assert Counter(b.meta.scenario for b in bundles) == {"rich": 3, "sparse": 3, "contradictory": 2, "stale": 2, "already_documented": 2}
    for path in tmp_path.glob("*.json"):
        bundle = SyntheticBundle.model_validate_json(path.read_text())
        assert bundle.source_documents
        assert bundle.meta.label == "SYNTHETIC"
        assert all("SYNTHETIC" in doc.excerpt for doc in bundle.source_documents)
        case = normalize(bundle)
        assert case.source_documents == sorted(case.source_documents, key=lambda d: (d.date, d.doc_id))


def test_normalization_deduplicates_and_rejects_conflicts(rich_bundle):
    rich_bundle.source_documents.append(rich_bundle.source_documents[0].model_copy(deep=True))
    assert len(normalize(rich_bundle).source_documents) == len(rich_bundle.source_documents)-1
    rich_bundle.source_documents[-1].excerpt = "Conflicting content"
    with pytest.raises(ValueError, match="Conflicting duplicate"):
        normalize(rich_bundle)


def test_future_records_rejected(rich_bundle):
    rich_bundle.source_documents[0].date = date(2027, 1, 1)
    rich_bundle.encounters[0].date = date(2027, 1, 1)
    with pytest.raises(ValueError, match="Future-dated"):
        normalize(rich_bundle)


def test_completeness_is_availability_not_diagnosis(rich_bundle):
    rich = normalize(rich_bundle)
    sparse = normalize(make_bundle(4, "sparse", []))
    assert rich.record_completeness == 1.0
    assert sparse.record_completeness == 0.4
    assert round(sum(rich.completeness_components.values()), 2) == rich.record_completeness


def test_two_sided_retrieval_surfaces_later_negation(contradictory_bundle):
    case = normalize(contradictory_bundle)
    candidates, _ = retrieve(case, run_rules(case).candidates)
    kidney = next(c for c in candidates if c.condition_key == "ckd")
    assert kidney.evidence_for and kidney.evidence_against
    assert any("ruled out" in e.detail and e.source_doc_id == "SYN-007-ckd-review" for e in kidney.evidence_against)
    assert max(e.date for e in kidney.evidence_against) > max(e.date for e in kidney.evidence_for)
    assert all(e.recency_days == (AS_OF-e.date).days for e in kidney.evidence_against)
    assert all(not e.source_doc_id.startswith("KB-") for e in kidney.evidence_for + kidney.evidence_against)


def test_negation_scope_does_not_cross_condition_sentences():
    doc = SourceDoc(doc_id="D1", doc_type="encounter_note", date=AS_OF,
        excerpt="SYNTHETIC. Clinician documents chronic kidney disease. Atrial fibrillation ruled out on tracing review.")
    assert classify_doc(doc, "ckd") == "for"
    assert classify_doc(doc, "af") == "against"


def test_isolated_lab_never_becomes_disease_suggestion(rich_bundle, tmp_path):
    rich_bundle.encounters = [e for e in rich_bundle.encounters if e.source_doc_id != "SYN-001-ckd-history"]
    rich_bundle.source_documents = [d for d in rich_bundle.source_documents if d.doc_id != "SYN-001-ckd-history"]
    result = run_pipeline(rich_bundle, condition_keys=["ckd"], audit_dir=tmp_path)
    assert result.brief.findings[0].status == "insufficient_evidence"
    assert result.brief.findings[0].evidence_for == []
    assert result.brief.care_gaps  # Dated lab review remains visible as record context.


def test_stale_without_superseding_note_abstains(tmp_path):
    bundle = make_bundle(9, "stale", ["ckd"])
    bundle.encounters = [e for e in bundle.encounters if e.source_doc_id != "SYN-009-ckd-review"]
    bundle.source_documents = [d for d in bundle.source_documents if d.doc_id != "SYN-009-ckd-review"]
    finding = run_pipeline(bundle, condition_keys=["ckd"], audit_dir=tmp_path).brief.findings[0]
    assert finding.status == "insufficient_evidence"
    assert finding.evidence_for == []
    assert "stale_historical_evidence" in finding.flags


@pytest.mark.parametrize("index,keys", [(11, ["ckd", "diabetes", "chf"]), (12, ["copd", "af", "depression"])])
def test_already_documented_never_resuggested(tmp_path, index, keys):
    result = run_pipeline(make_bundle(index, "already_documented", keys), audit_dir=tmp_path)
    selected = [f for f in result.brief.findings if f.condition_key in keys]
    assert len(selected) == 3
    assert all(f.status == "already_documented" and f.recommended_action == "already_on_chart" for f in selected)


def test_diabetes_record_gap_is_missing_documentation_not_overdue_care(tmp_path):
    bundle = make_bundle(11, "already_documented", ["diabetes"])
    for observation in bundle.observations:
        observation.date = date(2024, 5, 1)
        next(d for d in bundle.source_documents if d.doc_id == observation.source_doc_id).date = observation.date
    result = run_pipeline(bundle, audit_dir=tmp_path)
    gap = next(g for g in result.brief.care_gaps if g.gap_id == "diabetes-hba1c-record")
    assert "care may have occurred elsewhere" in gap.reason
    assert gap.recommended_action == "request_records"


@pytest.mark.parametrize("text,key,expected", [
    ("Clinician documents no diabetes.", "diabetes", "context"),
    ("Clinician documents hypertension. Family history of diabetes.", "diabetes", "context"),
    ("Clinician documents CKD; COPD was ruled out.", "ckd", "for"),
    ("Clinician documents CKD; COPD was ruled out.", "copd", "against"),
    ("Clinician documents possible diabetes.", "diabetes", "context"),
])
def test_target_specific_clauses_abstain_on_uncertain_or_unrelated_prose(text, key, expected):
    doc = SourceDoc(doc_id="D-review", doc_type="encounter_note", date=AS_OF, excerpt="SYNTHETIC. " + text)
    assert classify_doc(doc, key) == expected


def test_newer_provisional_note_cannot_revive_negated_old_documentation(tmp_path):
    bundle = make_bundle(4, "sparse", [])
    for doc_id, day, text in [
        ("affirmed", "2026-05-01", "Clinician documents chronic kidney disease."),
        ("negated", "2026-06-01", "Chronic kidney disease ruled out."),
        ("provisional", "2026-07-01", "Provisional concern for chronic kidney disease."),
    ]:
        bundle.source_documents.append(SourceDoc(doc_id=doc_id, doc_type="encounter_note", date=day, excerpt="SYNTHETIC. " + text))
    finding = run_pipeline(bundle, condition_keys=["ckd"], audit_dir=tmp_path).brief.findings[0]
    assert finding.status == "contradicted"
    assert finding.recommended_action == "no_action"


def test_structured_observation_cannot_disagree_with_source(rich_bundle):
    rich_bundle.observations[0].value = 14
    with pytest.raises(ValueError, match="not substantiated"):
        normalize(rich_bundle)


def test_structured_observation_date_must_match_source(rich_bundle):
    rich_bundle.observations[0].date = date(2026, 9, 1)
    with pytest.raises(ValueError, match="date differs"):
        normalize(rich_bundle)


def test_chart_code_requires_matching_source_content(rich_bundle):
    from dayone.schemas import CodedCondition
    rich_bundle.coded_conditions.append(CodedCondition(condition_key="depression", code="F32.A", display="Depression", date="2026-08-25", source_doc_id="SYN-001-intake"))
    with pytest.raises(ValueError, match="chart condition not substantiated"):
        normalize(rich_bundle)
