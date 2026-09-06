"""Run the full offline pipeline once per member, then score 30 fixed labels."""

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from dayone.generate import ROOT, generate
from dayone.pipeline import run_pipeline
from dayone.schemas import ConditionKey, Contract, Status
from .metrics import compute_metrics


class GoldenCase(Contract):
    case_id: str
    member_id: str
    condition_key: ConditionKey
    category: Literal["SUPPORTED", "ABSENT", "CONTRADICTED", "ADVERSARIAL", "STALE"]
    expected_status: Status
    rationale: str


class GoldenSet(Contract):
    version: str
    note: str
    cases: list[GoldenCase] = Field(min_length=30, max_length=30)

    @model_validator(mode="after")
    def category_contract(self):
        counts = Counter(c.category for c in self.cases)
        if counts != {"SUPPORTED": 8, "ABSENT": 8, "CONTRADICTED": 6, "ADVERSARIAL": 4, "STALE": 4}:
            raise ValueError("Golden-set categories must match the specified 8/8/6/4/4 split")
        if len({c.case_id for c in self.cases}) != 30 or len({(c.member_id, c.condition_key) for c in self.cases}) != 30:
            raise ValueError("Golden cases must have distinct identities and member/topic pairs")
        if len({c.member_id for c in self.cases}) != 12:
            raise ValueError("The golden set must cover all 12 synthetic members")
        return self


def markdown_table(result: dict) -> str:
    pct = lambda value: f"{value:.1%}" if value is not None else "N/A"
    lines = ["| Record status | Precision | Recall | F1 | Cases |", "|---|---:|---:|---:|---:|"]
    for row in result["per_status"]:
        lines.append(f"| {row['status']} | {pct(row['precision'])} | {pct(row['recall'])} | {pct(row['f1'])} | {row['support']} |")
    summary = result["summary"]
    lines += ["", f"Unsupported abstention: {pct(summary['abstention_rate'])} ({summary['abstention_numerator']}/{summary['abstention_denominator']}).",
        f"Contradiction detection: {pct(summary['contradiction_detection_rate'])} ({summary['contradiction_numerator']}/{summary['contradiction_denominator']}).",
        f"Unsafe suggestions: {pct(summary['unsafe_suggestion_rate'])}; citation accuracy: {pct(summary['citation_accuracy'])}.",
        f"Descriptive ECE: {summary['expected_calibration_error']:.3f}; confidence is uncalibrated.",
        "30 synthetic cases. This is a regression harness, not a validation study."]
    return "\n".join(lines)


def calibration_svg(result: dict) -> str:
    dots = []
    for item in result["calibration_bins"]:
        if item["count"]:
            x, y = 50+330*item["mean_confidence"], 360-300*item["observed_accuracy"]
            dots.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="7" fill="#bd5a38"/><text x="{x:.2f}" y="{y-14:.2f}" text-anchor="middle" font-size="12">n={item["count"]}</text>')
    return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 450 450" role="img" aria-label="Uncalibrated heuristic confidence compared with observed synthetic status accuracy"><rect width="450" height="450" fill="#faf8f3"/><g font-family="system-ui" fill="#282622"><text x="20" y="25" font-size="16">Heuristic confidence · 30 synthetic cases</text><path d="M50 60V360H380" fill="none" stroke="#555"/><path d="M50 360L380 60" fill="none" stroke="#aaa" stroke-dasharray="5 5"/><text x="42" y="382">0</text><text x="372" y="382">1</text><text x="25" y="65">1</text><text x="140" y="405">Mean heuristic confidence</text><text transform="translate(16 290) rotate(-90)">Observed status accuracy</text>'+''.join(dots)+'<text x="20" y="435" font-size="12">Descriptive only; no held-out clinical calibration.</text></g></svg>'


def run_evaluation(*, output: Path | None = None, audit_dir: Path | None = None) -> dict:
    golden = GoldenSet.model_validate_json((ROOT / "evaluation/golden_set.json").read_text())
    if not (ROOT / "data/synthetic/SYN-001.json").exists():
        generate()
    runs = {member: run_pipeline(ROOT / f"data/synthetic/{member}.json", audit_dir=audit_dir) for member in sorted({c.member_id for c in golden.cases})}
    rows = []
    for case in golden.cases:
        finding = next(f for f in runs[case.member_id].brief.findings if f.condition_key == case.condition_key)
        rows.append({**case.model_dump(), "predicted_status": finding.status, "confidence": finding.confidence, "correct": finding.status == case.expected_status})
    all_findings = [f.model_dump(mode="json") for run in runs.values() for f in run.brief.findings]
    docs = {doc.doc_id: doc.model_dump(mode="json") for run in runs.values() for doc in run.case.source_documents}
    member_runs = [{"member_id": member, "latency_ms": run.latency_ms, "estimated_cost_usd": run.estimated_cost_usd, "llm_called": run.audit.llm["called"]} for member, run in runs.items()]
    result = compute_metrics(rows, all_findings, docs, member_runs)
    result.update(synthetic=True, generated_at=datetime.now(timezone.utc).isoformat(), as_of="2026-09-06", mode="offline deterministic + keyword retrieval", golden_set_version=golden.version)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2) + "\n")
        output.with_name("calibration.svg").write_text(calibration_svg(result))
    mismatches = [r for r in rows if not r["correct"]]
    if mismatches:
        raise AssertionError("Golden regression failed: " + ", ".join(r["case_id"] for r in mismatches))
    return result


if __name__ == "__main__":
    result = run_evaluation(output=ROOT / "evaluation/results.json")
    print(markdown_table(result))
