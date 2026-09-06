from datetime import date
import json

import pytest
from pydantic import ValidationError

from dayone.authorize import assert_permission, authorize
from dayone.deterministic import run_rules
from dayone.normalize import normalize
from dayone.reason import baseline
from dayone.schemas import Finding


def payload(bundle):
    return baseline(run_rules(normalize(bundle), ["ckd"]).candidates[0]).model_dump(mode="json")


def test_suggestion_without_support_rejected(rich_bundle):
    value = payload(rich_bundle)
    value["evidence_for"] = []
    with pytest.raises(ValidationError, match="requires supporting evidence"):
        Finding.model_validate(value)


def test_abstention_cannot_carry_support(rich_bundle):
    value = payload(rich_bundle)
    value["status"] = "insufficient_evidence"
    with pytest.raises(ValidationError, match="empty evidence_for"):
        Finding.model_validate(value)


@pytest.mark.parametrize("confidence", [-0.01, 1.01, float("nan"), float("inf")])
def test_confidence_range(rich_bundle, confidence):
    value = payload(rich_bundle)
    value["confidence"] = confidence
    with pytest.raises(ValidationError):
        Finding.model_validate(value)


def test_low_confidence_cannot_request_confirmation(rich_bundle):
    value = payload(rich_bundle)
    value.update(confidence=0.49, recommended_action="flag_for_physician_confirmation")
    with pytest.raises(ValidationError, match="Low-confidence"):
        Finding.model_validate(value)


def test_uncited_or_long_reasoning_rejected(rich_bundle):
    value = payload(rich_bundle)
    value["reasoning"] = "Unsupported claim without a document id."
    with pytest.raises(ValidationError, match="reference a supplied"):
        Finding.model_validate(value)
    value["reasoning"] = "SYN-001-ckd-history supports review. One. Two."
    with pytest.raises(ValidationError, match="two sentences"):
        Finding.model_validate(value)


@pytest.mark.parametrize("confidence,expected", [(0.49, "request_records"), (0.69, "request_records"), (0.70, "flag_for_physician_confirmation")])
def test_authorization_threshold_and_human_review(rich_bundle, confidence, expected):
    value = payload(rich_bundle)
    value.update(confidence=confidence, automation_level="reversible_action", human_review_required=False)
    authorized = authorize(Finding.model_validate(value))
    assert authorized.recommended_action == expected
    assert authorized.automation_level == "recommend_only"
    assert authorized.human_review_required


def test_irreversible_action_is_explicitly_forbidden():
    with pytest.raises(AssertionError, match="Irreversible"):
        assert_permission("irreversible_action")
    with pytest.raises(PermissionError):
        assert_permission("reversible_action")


def test_missing_fields_or_extra_fields_fail(rich_bundle):
    value = payload(rich_bundle)
    value["diagnosis_order"] = "write chart"
    with pytest.raises(ValidationError):
        Finding.model_validate(value)
