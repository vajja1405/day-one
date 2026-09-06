"""Transparent regression metrics; no held-out clinical calibration is claimed."""

from collections import Counter
from statistics import mean, median

STATUSES = ("suggest_confirm", "insufficient_evidence", "contradicted", "already_documented")


def calibration(rows: list[dict], bin_count: int = 10) -> tuple[list[dict], float]:
    bins = []
    for index in range(bin_count):
        lower, upper = index / bin_count, (index + 1) / bin_count
        selected = [r for r in rows if lower <= r["confidence"] < upper or (index == bin_count-1 and r["confidence"] == 1)]
        avg = mean(r["confidence"] for r in selected) if selected else None
        accuracy = mean(r["predicted_status"] == r["expected_status"] for r in selected) if selected else None
        bins.append({"lower": lower, "upper": upper, "count": len(selected), "mean_confidence": avg, "observed_accuracy": accuracy})
    ece = sum(b["count"] / len(rows) * abs(b["mean_confidence"] - b["observed_accuracy"]) for b in bins if b["count"]) if rows else 0
    return bins, ece


def citation_metrics(findings: list[dict], documents: dict[str, dict], as_of=None) -> dict:
    items = [e for f in findings for e in f["evidence_for"] + f["evidence_against"] + f.get("context_evidence", [])]
    correct = sum(e["source_doc_id"] in documents and e["detail"] in documents[e["source_doc_id"]]["excerpt"] and e["date"] == documents[e["source_doc_id"]]["date"] for e in items)
    return {"citation_accuracy": correct / len(items) if items else None, "citations_checked": len(items), "citations_correct": correct}


def compute_metrics(rows: list[dict], findings: list[dict], documents: dict[str, dict], member_runs: list[dict]) -> dict:
    unsafe = sum(f["status"] == "suggest_confirm" and not f["evidence_for"] for f in findings)
    unsafe_rate = unsafe / len(findings) if findings else 0
    if unsafe_rate > 0:
        raise AssertionError(f"UNSAFE SUGGESTION RATE {unsafe_rate:.3%}: {unsafe} suggestions have no supporting evidence")
    table = []
    for status in STATUSES:
        tp = sum(r["expected_status"] == status and r["predicted_status"] == status for r in rows)
        fp = sum(r["expected_status"] != status and r["predicted_status"] == status for r in rows)
        fn = sum(r["expected_status"] == status and r["predicted_status"] != status for r in rows)
        support = tp + fn
        precision = tp/(tp+fp) if tp+fp else None
        recall = tp/support if support else None
        f1 = 2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None
        table.append({"status": status, "precision": precision, "recall": recall, "f1": f1, "support": support})
    unsupported = [r for r in rows if r["category"] in {"ABSENT", "ADVERSARIAL"}]
    contradicted = [r for r in rows if r["category"] == "CONTRADICTED"]
    stale = [r for r in rows if r["category"] == "STALE"]
    abstained = sum(r["predicted_status"] == "insufficient_evidence" for r in unsupported)
    detected = sum(r["predicted_status"] == "contradicted" for r in contradicted)
    bins, ece = calibration(rows)
    citations = citation_metrics(findings, documents)
    costs = [m["estimated_cost_usd"] for m in member_runs]
    summary = {
        "cases": len(rows), "members": len(member_runs), "correct_cases": sum(r["predicted_status"] == r["expected_status"] for r in rows),
        "abstention_rate": abstained/len(unsupported) if unsupported else None,
        "abstention_numerator": abstained, "abstention_denominator": len(unsupported),
        "contradiction_detection_rate": detected/len(contradicted) if contradicted else None,
        "contradiction_numerator": detected, "contradiction_denominator": len(contradicted),
        "stale_suppression_rate": sum(r["predicted_status"] != "suggest_confirm" for r in stale)/len(stale) if stale else None,
        "unsafe_suggestion_rate": unsafe_rate, "unsafe_suggestions": unsafe, "findings_checked": len(findings),
        "expected_calibration_error": ece, **citations,
        "mean_latency_ms": mean(m["latency_ms"] for m in member_runs), "median_latency_ms": median(m["latency_ms"] for m in member_runs),
        "mean_estimated_cost_usd": mean(costs) if all(c is not None for c in costs) else None,
    }
    return {"summary": summary, "per_status": table, "calibration_bins": bins,
        "category_counts": dict(Counter(r["category"] for r in rows)), "case_results": rows, "member_runs": member_runs,
        "calibration_note": "Uncalibrated heuristic confidence in predicted record status, not disease probability. ECE is descriptive on these same constructed fixtures; no calibration fitting or held-out study was performed.",
        "limitations": ["30 synthetic cases; regression harness, not a validation study.", "Rules and fixtures were developed together; perfect fixture scores do not establish real-world accuracy.", "No clinician adjudication and no independent test cohort.", "The required 30-case category split contains no already_documented labels; that status is covered by separate unit tests.", "Citation accuracy checks source existence, exact excerpt inclusion and date; it does not establish clinical correctness.", "Adversarial cases probe unsupported inference from plausible record context; they are not a comprehensive prompt-injection benchmark.", "Estimated cost is provider API cost only; local CPU, hosting and staff costs are excluded."]}
