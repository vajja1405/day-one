"""Precompute the entire demo: no backend or API key can fail during an interview.

The website reads these JSON fixtures. Build-time processing makes the demo
reliable without a model, while preserving complete dated evidence and audits.
Run --output /path/to/site/public/data to target another Sites/Vite checkout.
"""

import argparse
from collections import Counter
import json
from pathlib import Path

from dayone.generate import ROOT, generate
from dayone.pipeline import run_pipeline
from evaluation.run_eval import run_evaluation


def export(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    for name in ("briefs", "records", "audits"):
        (output / name).mkdir(exist_ok=True)
    bundles = generate()
    summaries, sample = [], None
    for bundle in bundles:
        result = run_pipeline(bundle)
        member = bundle.member_id
        summaries.append({"member_id": member, "age_band": bundle.demographics.age_band, "sex": bundle.demographics.sex,
            "scenario": bundle.meta.scenario, "record_completeness": result.case.record_completeness,
            "findings_count": len(result.brief.findings), "status_counts": dict(Counter(f.status for f in result.brief.findings)),
            "synthetic": True, "source_document_count": len(result.case.source_documents)})
        for folder, value in (("briefs", result.brief), ("records", result.case), ("audits", result.audit)):
            (output / folder / f"{member}.json").write_text(value.model_dump_json(indent=2) + "\n")
        if member == "SYN-007":
            sample = result.audit
    (output / "members.json").write_text(json.dumps(summaries, indent=2) + "\n")
    (output / "audit_sample.json").write_text(sample.model_dump_json(indent=2) + "\n")
    evaluation = run_evaluation(output=ROOT / "evaluation/results.json")
    (output / "evaluation.json").write_text(json.dumps(evaluation, indent=2) + "\n")
    (output / "manifest.json").write_text(json.dumps({"synthetic": True, "as_of": "2026-09-06", "default_member": "SYN-007", "member_count": len(summaries), "schema_version": "0.1.0", "confidence_note": "Uncalibrated heuristic confidence in record status, not disease probability.", "mode": "precomputed offline fixtures; no API key or backend"}, indent=2) + "\n")
    return evaluation


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "site/public/data")
    args = parser.parse_args()
    export(args.output)
    print(f"Exported 12 synthetic briefs, records, audits and 30-case evaluation to {args.output}")
