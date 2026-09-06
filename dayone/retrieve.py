"""Two-sided member-record retrieval, exact terms first, cached semantics second.

Public reference snippets remain contextual knowledge, never patient evidence.
Optional all-MiniLM-L6-v2 + FAISS IndexFlatIP is loaded only from a caller-supplied
local cache; ordinary offline runs require neither weights nor these packages.
"""

import json
import os
from pathlib import Path

from .deterministic import ALIASES, classify_doc, evidence, mentions
from .generate import ROOT
from .schemas import Candidate, CaseObject, KnowledgeSnippet


def load_knowledge(path: Path | None = None) -> tuple[dict, list[KnowledgeSnippet]]:
    raw = json.loads((path or ROOT / "data/knowledge/references.json").read_text())
    return raw, [KnowledgeSnippet.model_validate(item) for item in raw["snippets"]]


def _semantic_context(case: CaseObject, query: str, model_path: str):
    if not Path(model_path).is_dir():
        raise ValueError("Semantic model must be an existing local directory")
    # Lazy imports keep the default demonstration small and network-independent.
    from sentence_transformers import SentenceTransformer
    import faiss

    model = SentenceTransformer(model_path, local_files_only=True, trust_remote_code=False)
    vectors = model.encode([d.excerpt for d in case.source_documents], normalize_embeddings=True, convert_to_numpy=True)
    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors.astype("float32"))
    query_vector = model.encode([query], normalize_embeddings=True, convert_to_numpy=True).astype("float32")
    scores, ids = index.search(query_vector, min(3, len(case.source_documents)))
    return [case.source_documents[int(i)] for score, i in zip(scores[0], ids[0]) if i >= 0 and score >= 0.45]


def retrieve(case: CaseObject, candidates: list[Candidate], knowledge_path: Path | None = None) -> tuple[list[Candidate], list[str]]:
    _, knowledge = load_knowledge(knowledge_path)
    outputs, fallbacks = [], []
    for original in candidates:
        candidate = original.model_copy(deep=True)
        matched = []
        # Explicitly search both topic wording and negation/resolution in the same record.
        for doc in case.source_documents:
            if not mentions(doc.excerpt, candidate.condition_key):
                continue
            matched.append(doc)
            role = classify_doc(doc, candidate.condition_key)
            item = evidence(doc, case)
            destination = candidate.evidence_against if role == "against" else candidate.evidence_for if role in {"for", "historical"} else candidate.context_evidence
            if item.source_doc_id not in {e.source_doc_id for e in destination}:
                destination.append(item)
        model_path = os.environ.get("DAYONE_SEMANTIC_MODEL_PATH")
        if not matched and model_path:
            try:
                semantic = _semantic_context(case, " ".join(ALIASES[candidate.condition_key]) + " ruled out resolved transient no evidence of normalised discontinued", model_path)
                # Similarity alone must not turn an unrelated passage into supporting evidence.
                candidate.context_evidence.extend(evidence(doc, case) for doc in semantic)
                candidate.retrieval_method = "cached_semantic_context"
            except (ImportError, OSError, ValueError, RuntimeError) as exc:
                fallbacks.append(f"semantic_unavailable:{type(exc).__name__}; keyword retrieval retained")
        candidate.knowledge = [snippet for snippet in knowledge if snippet.condition_key == candidate.condition_key]
        for field in ("evidence_for", "evidence_against", "context_evidence"):
            unique = {item.source_doc_id: item for item in getattr(candidate, field)}
            setattr(candidate, field, sorted(unique.values(), key=lambda e: (e.date, e.source_doc_id)))
        outputs.append(candidate)
    return outputs, sorted(set(fallbacks))
