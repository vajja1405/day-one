"""Run Day One against controlled, auditable fragmentation.

This is deliberately a characterization harness. It does not repair records,
choose a better threshold, or let Shatter's private ground-truth context enter
the Day One pipeline. A pipeline validation error is recorded as an ingestion
failure rather than silently discarded.
"""

from __future__ import annotations

import argparse
import json
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

from dayone.generate import ROOT, CONDITIONS
from dayone.pipeline import run_pipeline
from evaluation.shatter_fixtures import as_bundle, fixtures
from shatter.engine import shatter
from shatter.modes import MODES


def _rate(n: int, d: int) -> float | None:
    return round(n / d, 4) if d else None


def _run_case(record: dict, severity: float, seed: int, modes: list[str], audit_root: Path) -> dict:
    bundle = as_bundle(record)
    bundle["_shatter"] = record["_shatter"]
    fragmented, report = shatter(bundle, severity=severity, modes=modes, seed=seed)
    result = {
        "member_id": report.member_id,
        "severity": severity,
        "seed": seed,
        "events": len(report.events),
        "fired": report.fired,
        "ground_truth": report.ground_truth,
        "pipeline_valid": False,
        "predictions": {},
        "citation_integrity": 0.0,
        "identity_resolution_accuracy": 0.0 if report.fired.get("identity_drift") else 1.0,
        "error": None,
        "report": report.model_dump(mode="json"),
    }
    try:
        run = run_pipeline(fragmented, audit_dir=audit_root / f"{report.member_id}-{seed}-{severity:.1f}")
        result["pipeline_valid"] = True
        result["predictions"] = {finding.condition_key: finding.status for finding in run.brief.findings}
        documents = {doc.doc_id: doc for doc in run.case.source_documents}
        evidence = [e for f in run.brief.findings for e in f.evidence_for + f.evidence_against + f.context_evidence]
        result["citation_integrity"] = 1.0 if all(
            e.source_doc_id in documents and e.date == documents[e.source_doc_id].date and e.detail in documents[e.source_doc_id].excerpt
            for e in evidence
        ) else 0.0
    except Exception as exc:  # The failure is part of the curve, not a lost row.
        result["error"] = f"{type(exc).__name__}: {str(exc).splitlines()[0]}"
    return result


def _score(rows: list[dict]) -> dict:
    unsupported = [(r, key) for r in rows for key, status in r["ground_truth"].items() if status in {"insufficient_evidence"}]
    false = [(r, key) for r in rows for key, predicted in r["predictions"].items() if predicted == "suggest_confirm" and r["ground_truth"].get(key) != "suggest_confirm"]
    contradictions = [(r, key) for r in rows for key, status in r["ground_truth"].items() if status == "contradicted"]
    abstained = sum(r["predictions"].get(key) == "insufficient_evidence" for r, key in unsupported)
    detected = sum(r["predictions"].get(key) == "contradicted" for r, key in contradictions)
    valid = [r for r in rows if r["pipeline_valid"]]
    return {
        "runs": len(rows),
        "pipeline_error_rate": round(sum(not r["pipeline_valid"] for r in rows) / len(rows), 4) if rows else 0.0,
        "abstention_rate_on_unsupported": _rate(abstained, len(unsupported)),
        "false_finding_rate": _rate(len(false), sum(len(r["ground_truth"]) for r in rows)),
        "citation_integrity": round(mean(r["citation_integrity"] for r in valid), 4) if valid else 0.0,
        "contradiction_detection_rate": _rate(detected, len(contradictions)),
        "identity_resolution_accuracy": round(mean(r["identity_resolution_accuracy"] for r in rows), 4) if rows else 0.0,
        "mean_events": round(mean(r["events"] for r in rows), 2) if rows else 0.0,
    }


def run_degradation(*, seeds: int = 20, output: Path | None = None) -> dict:
    if seeds < 1 or seeds > 100:
        raise ValueError("seeds must be between 1 and 100")
    records = fixtures()
    levels = [round(i / 10, 1) for i in range(11)]
    with tempfile.TemporaryDirectory(prefix="shatter-audit-") as temp:
        audit_root = Path(temp)
        curve = []
        for severity in levels:
            rows = [_run_case(record, severity, seed, list(MODES), audit_root) for seed in range(seeds) for record in records]
            curve.append({"severity": severity, **_score(rows)})
        per_mode = []
        for mode in MODES:
            rows = [_run_case(record, 0.6, seed, [mode], audit_root) for seed in range(seeds) for record in records]
            metrics = _score(rows)
            # A transparent ordering score: each term is a failure rate, not a
            # claim of clinical importance or a learned model score.
            damage = (
                (1 - (metrics["abstention_rate_on_unsupported"] or 0))
                + metrics["false_finding_rate"]
                + (1 - (metrics["contradiction_detection_rate"] or 0))
                + (1 - metrics["citation_integrity"])
                + metrics["pipeline_error_rate"]
            )
            per_mode.append({"mode": mode, "label": MODES[mode], "damage_score": round(damage, 4), "metrics": metrics})
        per_mode.sort(key=lambda item: item["damage_score"], reverse=True)
        worst = per_mode[0]["mode"] if per_mode else None
        walkthrough_record = records[6]
        walkthrough = _run_case(walkthrough_record, 0.6, 7, [worst] if worst else list(MODES), audit_root)
    result = {
        "version": "shatter-degradation-v1",
        "synthetic": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "as_of": "2026-09-06",
        "seeds_per_level": seeds,
        "member_count": len(records),
        "modes": [{"mode": key, "label": label} for key, label in MODES.items()],
        "curve": curve,
        "per_mode": per_mode,
        "worst_mode": worst,
        "walkthrough": walkthrough,
        "limitations": [
            "Every member, mutation, label and metric is synthetic and constructed for this regression harness.",
            "The modes are inferred from published failure patterns and general domain reading, not from observing a payer's data.",
            "A validation error means the current consumer rejected the fragmented bundle; it is counted as an ingestion failure.",
            "Identity accuracy is 1 when no identity drift was applied and 0 when it was applied because Day One has no identity resolver.",
            "The damage score only orders these ten declared modes; it is not a population prevalence or clinical severity estimate.",
        ],
    }
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2) + "\n")
        output.with_name("degradation.svg").write_text(render_svg(result))
    return result


def render_svg(result: dict) -> str:
    width, height, left, top, plot_w, plot_h = 740, 390, 60, 35, 640, 260
    lines = []
    metrics = [
        ("false_finding_rate", "False finding", "#bd5a38"),
        ("pipeline_error_rate", "Pipeline error", "#2949d5"),
        ("abstention_rate_on_unsupported", "Unsupported abstention", "#265647"),
    ]
    for key, label, color in metrics:
        points = []
        for row in result["curve"]:
            value = row.get(key) or 0
            x = left + row["severity"] * plot_w
            y = top + plot_h - value * plot_h
            points.append(f"{x:.1f},{y:.1f}")
        lines.append(f'<polyline fill="none" stroke="{color}" stroke-width="3" points="{" ".join(points)}"/><text x="{left+plot_w-4}" y="{points[-1].split(",")[1]}" text-anchor="end" font-size="12" fill="{color}">{label}</text>')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-label="Shatter degradation curves across synthetic fragmentation severity"><rect width="100%" height="100%" fill="#faf8f3"/><g font-family="system-ui" fill="#282622"><text x="{left}" y="20" font-size="16">Shatter · {result["seeds_per_level"]} seeds per level</text><path d="M{left} {top}V{top+plot_h}H{left+plot_w}" fill="none" stroke="#777"/><path d="M{left} {top+plot_h/2}H{left+plot_w}" stroke="#ddd"/><path d="M{left} {top+plot_h/4}H{left+plot_w}" stroke="#ddd"/><text x="{left-8}" y="{top+5}" text-anchor="end" font-size="11">1.0</text><text x="{left-8}" y="{top+plot_h/2+4}" text-anchor="end" font-size="11">0.5</text><text x="{left-8}" y="{top+plot_h+4}" text-anchor="end" font-size="11">0</text><text x="{left}" y="{top+plot_h+28}" font-size="11">0.0</text><text x="{left+plot_w}" y="{top+plot_h+28}" text-anchor="end" font-size="11">1.0</text><text x="{left+plot_w/2}" y="{height-12}" text-anchor="middle" font-size="12">Fragmentation severity</text>{''.join(lines)}<text x="{left}" y="{height-12}" font-size="11">Rates are synthetic harness measurements</text></g></svg>'''


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--output", type=Path, default=ROOT / "evaluation/degradation_results.json")
    args = parser.parse_args()
    result = run_degradation(seeds=args.seeds, output=args.output)
    print(json.dumps({"curve_levels": len(result["curve"]), "worst_mode": result["worst_mode"], "per_mode": result["per_mode"]}, indent=2))
