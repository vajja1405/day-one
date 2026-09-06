import json

import pytest

from dayone.audit import digest, validate_brief_sources, verify_chain
from dayone.deterministic import run_rules
from dayone.generate import ROOT, make_bundle
from dayone.normalize import normalize
from dayone.pipeline import run_pipeline
from dayone.reason import baseline, reason
from dayone.retrieve import retrieve
from evaluation.metrics import calibration, citation_metrics, compute_metrics
from evaluation.run_eval import GoldenSet, run_evaluation


def unresolved_candidate():
    bundle = make_bundle(9, "stale", ["ckd"])
    bundle.encounters = [e for e in bundle.encounters if e.source_doc_id != "SYN-009-ckd-review"]
    bundle.source_documents = [d for d in bundle.source_documents if d.doc_id != "SYN-009-ckd-review"]
    case = normalize(bundle)
    return retrieve(case, run_rules(case, ["ckd"]).candidates)[0][0]


def test_llm_retries_once_and_fails_closed():
    calls = []
    def invalid(messages, schema):
        calls.append(messages)
        return {"content": '{"findings":[{"status":"suggest_confirm"}]}'}
    result = reason([unresolved_candidate()], enabled=True, caller=invalid)
    assert len(calls) == 2 and result.validation_retries == 1
    assert result.findings[0].status == "insufficient_evidence"
    assert any("failed_closed" in item for item in result.fallbacks)


def test_altered_citation_date_is_rejected():
    candidate = unresolved_candidate()
    payload = baseline(candidate).model_dump(mode="json")
    payload["context_evidence"][0]["date"] = "2026-09-01"
    def fabricated(messages, schema):
        return {"content": json.dumps({"findings": [payload]})}
    result = reason([candidate], enabled=True, caller=fabricated)
    assert result.validation_retries == 1
    assert any("failed_closed" in item for item in result.fallbacks)


def test_model_prose_cannot_inject_unsupported_claims_or_permissions():
    candidate = unresolved_candidate()
    payload = baseline(candidate).model_dump(mode="json")
    source_id = payload["context_evidence"][0]["source_doc_id"]
    payload.update(reasoning=f"{source_id} proves an invented diagnosis and medication order.", automation_level="reversible_action", human_review_required=False)
    def model(messages, schema):
        return {"content": json.dumps({"findings": [payload]}), "usage": {"prompt_tokens": 10, "completion_tokens": 20}}
    result = reason([candidate], enabled=True, caller=model)
    assert result.llm_called and result.validation_retries == 0
    assert "invented diagnosis" not in result.findings[0].reasoning
    assert result.findings[0].automation_level == "recommend_only"
    assert result.findings[0].human_review_required


def test_model_never_called_for_rule_resolved_cases(rich_bundle):
    def forbidden(*args):
        pytest.fail("Model should not be called for a resolved case")
    result = reason(run_rules(normalize(rich_bundle)).candidates, enabled=True, caller=forbidden)
    assert result.llm_called is False


def test_network_is_not_required_offline(monkeypatch, rich_bundle, tmp_path):
    import socket
    monkeypatch.setattr(socket.socket, "connect", lambda *args: pytest.fail("Unexpected network call"))
    result = run_pipeline(rich_bundle, audit_dir=tmp_path)
    assert result.audit.llm["called"] is False
    assert result.estimated_cost_usd == 0


def test_append_only_audit_reconstructs_every_citation(rich_bundle, contradictory_bundle, tmp_path):
    first = run_pipeline(rich_bundle, audit_dir=tmp_path)
    original = (tmp_path / "runs.jsonl").read_bytes()
    second = run_pipeline(contradictory_bundle, audit_dir=tmp_path)
    assert (tmp_path / "runs.jsonl").read_bytes().startswith(original)
    records = [json.loads(line) for line in (tmp_path / "runs.jsonl").read_text().splitlines()]
    assert verify_chain(records)
    assert records[1]["previous_record_sha256"] == records[0]["record_sha256"]
    for run in (first, second):
        assert run.audit.brief_sha256 == digest(run.brief.model_dump(mode="json"))
        validate_brief_sources(run.brief, run.case)
        source_ids = {d["doc_id"] for d in run.audit.source_documents}
        for finding in run.brief.findings:
            assert all(e.source_doc_id in source_ids for e in finding.evidence_for + finding.evidence_against + finding.context_evidence)
        for source in run.audit.source_documents:
            actual = next(doc for doc in run.case.source_documents if doc.doc_id == source["doc_id"])
            assert source["sha256"] == digest(actual.model_dump(mode="json"))
    records[0]["member_id"] = "TAMPERED"
    assert not verify_chain(records)


def test_tampered_audit_cannot_be_extended(rich_bundle, tmp_path):
    run_pipeline(rich_bundle, audit_dir=tmp_path)
    path = tmp_path / "runs.jsonl"
    path.write_text(path.read_text().replace('"synthetic":true', '"synthetic":false', 1))
    with pytest.raises(ValueError, match="integrity"):
        run_pipeline(rich_bundle, audit_dir=tmp_path)


def test_full_golden_harness_and_exact_category_counts(tmp_path):
    golden = GoldenSet.model_validate_json((ROOT / "evaluation/golden_set.json").read_text())
    assert len(golden.cases) == 30
    result = run_evaluation(audit_dir=tmp_path)
    assert result["summary"]["correct_cases"] == 30
    assert result["summary"]["abstention_rate"] == 1
    assert result["summary"]["contradiction_detection_rate"] == 1
    assert result["summary"]["stale_suppression_rate"] == 1
    assert result["summary"]["unsafe_suggestion_rate"] == 0
    assert result["summary"]["citation_accuracy"] == 1
    assert result["summary"]["expected_calibration_error"] > 0  # Perfect fixture accuracy is not calibration.


def test_unsafe_metric_fails_loudly_before_any_other_metric():
    with pytest.raises(AssertionError, match="UNSAFE SUGGESTION RATE"):
        compute_metrics([], [{"status": "suggest_confirm", "evidence_for": []}], {}, [])


def test_citation_metric_does_not_credit_fabricated_detail():
    evidence = {"source_doc_id": "D1", "date": "2026-09-01", "detail": "invented detail"}
    result = citation_metrics([{"evidence_for": [evidence], "evidence_against": []}], {"D1": {"date": "2026-09-01", "excerpt": "actual detail"}})
    assert result["citation_accuracy"] == 0


def test_ece_bins_include_confidence_one_and_use_observed_accuracy():
    rows = [{"confidence": 1.0, "predicted_status": "suggest_confirm", "expected_status": "contradicted"},
            {"confidence": 0.5, "predicted_status": "contradicted", "expected_status": "contradicted"}]
    bins, ece = calibration(rows)
    assert sum(b["count"] for b in bins) == 2
    assert ece == pytest.approx(0.75)


def test_api_health_and_member_allowlist():
    from fastapi.testclient import TestClient
    from api.server import app
    client = TestClient(app)
    assert client.get("/health").json()["synthetic"]
    assert client.get("/members/UNKNOWN").status_code == 404
    assert client.get("/members/SYN-007").json()["synthetic"]
