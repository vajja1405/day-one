"""The model never determines its own permission. The software determines permission.

The ladder names capabilities; this implementation only exposes read, reason and
recommend. It has no clinical write, ordering, messaging or prescribing tools.
"""

from .schemas import Finding

LADDER = ("read", "reason", "recommend", "reversible_action", "irreversible_action")
POLICY = (
    {"status": "already_documented", "minimum_confidence": 0, "action": "already_on_chart", "review": False},
    {"status": "contradicted", "minimum_confidence": 0, "action": "no_action", "review": True},
    {"status": "insufficient_evidence", "minimum_confidence": 0, "action": "no_action", "review": False},
    {"status": "suggest_confirm", "minimum_confidence": 0.70, "action": "flag_for_physician_confirmation", "review": True},
    {"status": "suggest_confirm", "minimum_confidence": 0, "action": "request_records", "review": True},
)


def assert_permission(capability: str) -> None:
    # Deliberate invariant: even a future caller cannot authorize an irreversible act.
    if capability == "irreversible_action":
        raise AssertionError("Irreversible actions are forbidden in Day One")
    if capability not in {"read", "reason", "recommend"}:
        raise PermissionError("This prototype permits observation and recommendations only")


def authorize(finding: Finding) -> Finding:
    row = next(row for row in POLICY if row["status"] == finding.status and finding.confidence >= row["minimum_confidence"])
    assert_permission("recommend")
    payload = finding.model_dump()
    payload.update(recommended_action=row["action"], automation_level="recommend_only", human_review_required=row["review"])
    if finding.status == "suggest_confirm" and finding.confidence < 0.70:
        payload["flags"] = sorted(set(payload["flags"] + ["low_confidence_request_records"]))
    return Finding.model_validate(payload)
