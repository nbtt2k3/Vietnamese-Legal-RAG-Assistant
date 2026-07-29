from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class QueryIntent:
    raw_query: str
    normalized_query: str
    loai_yeu_cau: str = "general_legal_question"
    linh_vuc: list[str] = field(default_factory=list)
    chu_the: list[str] = field(default_factory=list)
    time_context: dict[str, Any] = field(default_factory=dict)
    source_preference: list[str] = field(default_factory=list)
    citation_targets: list[str] = field(default_factory=list)
    legal_roles: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    key_phrases: list[str] = field(default_factory=list)
    query_variants: list[str] = field(default_factory=list)
    source_priority: list[str] = field(default_factory=list)
    scenario_terms: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RetrievedChunk:
    chunk_id: str
    doc_id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    scores: dict[str, float] = field(default_factory=dict)
    sources: list[str] = field(default_factory=list)
    relevance_label: str = ""
    relevance_rank: int = 0

    def merge(self, other: "RetrievedChunk") -> None:
        for key, value in other.scores.items():
            self.scores[key] = max(self.scores.get(key, 0.0), value)
        for source in other.sources:
            if source not in self.sources:
                self.sources.append(source)
        if not self.metadata and other.metadata:
            self.metadata = other.metadata
        if not self.text and other.text:
            self.text = other.text

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EvidenceBundle:
    core_authorities: list[RetrievedChunk] = field(default_factory=list)
    supporting_authorities: list[RetrievedChunk] = field(default_factory=list)
    case_law_support: list[RetrievedChunk] = field(default_factory=list)
    temporal_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "core_authorities": [item.to_dict() for item in self.core_authorities],
            "supporting_authorities": [item.to_dict() for item in self.supporting_authorities],
            "case_law_support": [item.to_dict() for item in self.case_law_support],
            "temporal_notes": self.temporal_notes,
        }


@dataclass
class RetrievalResult:
    query_intent: QueryIntent
    candidates: list[RetrievedChunk] = field(default_factory=list)
    evidence: EvidenceBundle = field(default_factory=EvidenceBundle)
    confidence: dict[str, Any] = field(default_factory=dict)
    retrieval_debug: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query_intent": self.query_intent.to_dict(),
            "candidates": [item.to_dict() for item in self.candidates],
            "evidence": self.evidence.to_dict(),
            "confidence": self.confidence,
            "retrieval_debug": self.retrieval_debug,
        }
