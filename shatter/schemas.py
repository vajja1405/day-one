"""Reversible, hash-checked corruption reports; never clinical ground-truth inference."""
from copy import deepcopy
import hashlib
import json
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


class Patch(BaseModel):
    model_config = ConfigDict(extra='forbid')
    mode: str
    field: str
    existed_before: bool
    before: Any
    after: Any


class MutationEvent(BaseModel):
    mode: str
    target: str
    description: str
    original_span: str | None = None
    corrupted_span: str | None = None
    original_value: Any = None
    corrupted_value: Any = None
    original_source_doc_id: str | None = None


class FragmentationReport(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: str = 'shatter-v1'
    synthetic: Literal[True] = True
    member_id: str
    severity: float = Field(ge=0, le=1, allow_inf_nan=False)
    seed: int
    requested_modes: list[str]
    original_sha256: str
    fragmented_sha256: str
    patches: list[Patch]
    events: list[MutationEvent]
    eligibility: dict[str, int]
    fired: dict[str, int]
    ground_truth: dict[str, str] = Field(default_factory=dict)

    def restore(self, fragmented: dict) -> dict:
        """Reverse in application order and verify BOTH input and restored hashes."""
        if digest(fragmented) != self.fragmented_sha256:
            raise ValueError('Fragmented input does not match this report')
        result = deepcopy(fragmented)
        for patch in reversed(self.patches):
            if result.get(patch.field) != patch.after:
                raise ValueError('Patch history is inconsistent')
            if patch.existed_before:
                result[patch.field] = deepcopy(patch.before)
            else:
                result.pop(patch.field, None)
        if digest(result) != self.original_sha256:
            raise ValueError('Restored record does not match original hash')
        return result
