"""Append-only, hash-chained JSONL audit records with source and brief hashes.

Advisory process locking protects concurrent local writers. Hash chaining detects
accidental edits, but this is not a signed ledger or a production WORM store; a
filesystem administrator could replace the whole chain. Existing lines are never
rewritten by this application.
"""

import fcntl
import hashlib
import json
import os
from pathlib import Path

from .schemas import AuditRecord, CaseObject, DayOneBrief


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def validate_brief_sources(brief: DayOneBrief, case: CaseObject) -> None:
    docs = {d.doc_id: d for d in case.source_documents}
    evidence_items = [e for finding in brief.findings for e in finding.evidence_for + finding.evidence_against + finding.context_evidence]
    evidence_items += [e for gap in brief.care_gaps for e in gap.evidence]
    evidence_items += [e for flag in brief.medication_flags for e in flag.evidence]
    for item in evidence_items:
        doc = docs.get(item.source_doc_id)
        if doc is None or item.date != doc.date or item.detail not in doc.excerpt:
            raise ValueError(f"Ungrounded citation: {item.source_doc_id}")
        if item.recency_days != (case.as_of-doc.date).days:
            raise ValueError(f"Incorrect citation recency: {item.source_doc_id}")
    for gap in brief.care_gaps:
        if set(gap.reviewed_source_doc_ids) - set(docs):
            raise ValueError("Care-gap review refers to an unknown source")


def verify_chain(records: list[dict]) -> bool:
    previous = None
    for record in records:
        expected = record.get("record_sha256")
        data = {key: value for key, value in record.items() if key != "record_sha256"}
        if data.get("previous_record_sha256") != previous or digest(data) != expected:
            return False
        previous = expected
    return True


def append_audit(record: AuditRecord, directory: Path) -> AuditRecord:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "runs.jsonl"
    # O_APPEND prevents an ordinary writer from replacing previous bytes.
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, "a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        handle.seek(0)
        records = [json.loads(line) for line in handle if line.strip()]
        if not verify_chain(records):
            raise ValueError("Audit chain failed integrity verification; refusing to append")
        payload = record.model_dump(mode="json")
        payload["previous_record_sha256"] = records[-1]["record_sha256"] if records else None
        payload.pop("record_sha256", None)
        payload["record_sha256"] = digest(payload)
        sealed = AuditRecord.model_validate(payload)
        handle.write(canonical(sealed.model_dump(mode="json")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    return sealed
