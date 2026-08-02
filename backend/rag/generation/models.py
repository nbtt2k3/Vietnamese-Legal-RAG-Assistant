from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class CitationRecord:
    citation: str
    snippet: str
    source_type: str
    evidence_id: str = ""
    legal_role: str = ""
    validity_status: str = ""
    source_verification_status: str = ""
    source_url: str = ""
    source_file: str = ""
    source_of_validity: str = ""
    validity_basis: str = ""
    validity_confidence: str = ""
    page_start: int | None = None
    page_end: int | None = None
    relevance_score: float = 0.0
    relevance_label: str = ""
    relevance_rank: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Claim:
    statement: str
    reasoning: str
    evidence_ids: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass
class AnswerSection:
    title: str
    content: str
    citations: list[CitationRecord] = field(default_factory=list)
    claims: list[Claim] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "content": self.content,
            "citations": [item.to_dict() for item in self.citations],
            "claims": [item.to_dict() for item in self.claims],
        }


@dataclass
class LegalAnswer:
    query: str
    short_answer: str
    sections: list[AnswerSection] = field(default_factory=list)
    citations: list[CitationRecord] = field(default_factory=list)
    confidence: dict[str, Any] = field(default_factory=dict)
    disclaimers: list[str] = field(default_factory=list)
    retrieval_debug: dict[str, Any] = field(default_factory=dict)
    answer_method: str = "rule_based"

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "short_answer": self.short_answer,
            "sections": [item.to_dict() for item in self.sections],
            "citations": [item.to_dict() for item in self.citations],
            "confidence": self.confidence,
            "disclaimers": self.disclaimers,
            "retrieval_debug": self.retrieval_debug,
            "answer_method": self.answer_method,
        }
