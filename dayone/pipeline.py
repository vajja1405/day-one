"""Seven visible steps: normalize → rules → retrieve → reason → authorize → brief → audit."""

import argparse
from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from .audit import append_audit, digest, validate_brief_sources
from .authorize import authorize
from .deterministic import run_rules
from .generate import ROOT
from .normalize import AS_OF, normalize
from .reason import reason
from .retrieve import load_knowledge, retrieve
from .schemas import AuditRecord, CaseObject, Contract, DayOneBrief, SyntheticBundle


class PipelineResult(Contract):
    brief: DayOneBrief
    audit: AuditRecord
    case: CaseObject
    latency_ms: float
    estimated_cost_usd: float | None


def run_pipeline(bundle: SyntheticBundle | dict | Path, *, as_of: date = AS_OF,
                 condition_keys: list[str] | None = None, audit_dir: Path | None = None,
                 llm_enabled: bool = False, llm_caller=None) -> PipelineResult:
    started = perf_counter()
    case = normalize(bundle, as_of)                                      # 1. normalize
    rules = run_rules(case, condition_keys)                              # 2. deterministic first
    candidates, retrieval_fallbacks = retrieve(case, rules.candidates)    # 3. two-sided retrieval
    reasoning = reason(candidates, enabled=llm_enabled, caller=llm_caller) # 4. constrained reasoning
    findings = [authorize(finding) for finding in reasoning.findings]     # 5. software permissions
    timestamp = datetime.now(timezone.utc)
    audit_id = f"audit-{uuid4()}"
    brief = DayOneBrief(member_id=case.member_id, generated_at=timestamp, as_of=as_of,
        record_completeness=case.record_completeness, findings=findings, care_gaps=rules.care_gaps,
        medication_flags=rules.medication_flags, unknowns=rules.unknowns, audit_id=audit_id) # 6. brief
    validate_brief_sources(brief, case)
    knowledge, _ = load_knowledge()
    audit = AuditRecord(audit_id=audit_id, timestamp=timestamp, as_of=as_of, member_id=case.member_id,
        source_documents=[{"doc_id": d.doc_id, "date": d.date.isoformat(), "doc_type": d.doc_type,
            "sha256": digest(d.model_dump(mode="json")), "excerpt": d.excerpt} for d in case.source_documents],
        knowledge_base_version=knowledge["version"], knowledge_base_sha256=digest(knowledge),
        deterministic_rules_fired=rules.rules_fired,
        llm={"called": reasoning.llm_called, "model": reasoning.model, "prompt_hash": reasoning.prompt_hash,
             "validation_retries": reasoning.validation_retries, "usage": reasoning.usage},
        candidate_outcomes=[{"candidate": c.model_dump(mode="json"), "final_status": f.status,
                             "final_finding": f.model_dump(mode="json")} for c, f in zip(candidates, findings)],
        authorization=[{"finding_id": f.finding_id, "permitted_capability": "recommend", "automation_level": f.automation_level,
            "recommended_action": f.recommended_action, "human_review_required": f.human_review_required} for f in findings],
        fallbacks=retrieval_fallbacks + reasoning.fallbacks, brief_sha256=digest(brief.model_dump(mode="json")), previous_record_sha256=None)
    audit = append_audit(audit, audit_dir or ROOT / "data/audit")          # 7. append-only audit
    input_price, output_price = os.environ.get("DAYONE_INPUT_COST_PER_MILLION"), os.environ.get("DAYONE_OUTPUT_COST_PER_MILLION")
    cost = 0.0 if not reasoning.llm_called else None
    if reasoning.llm_called and input_price and output_price and reasoning.usage:
        cost = (reasoning.usage.get("prompt_tokens", 0) * float(input_price) + reasoning.usage.get("completion_tokens", 0) * float(output_price)) / 1_000_000
    return PipelineResult(brief=brief, audit=audit, case=case, latency_ms=round((perf_counter()-started)*1000, 3), estimated_cost_usd=cost)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate an evidence-cited SYNTHETIC record-review brief")
    parser.add_argument("--member", default="SYN-007", choices=[f"SYN-{n:03d}" for n in range(1, 13)])
    parser.add_argument("--llm", action="store_true", help="Explicitly enable optional configured compatible LLM")
    args = parser.parse_args()
    result = run_pipeline(ROOT / f"data/synthetic/{args.member}.json", llm_enabled=args.llm)
    print(result.brief.model_dump_json(indent=2))
