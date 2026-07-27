import re

from generation.models import CitationRecord
from retrieval.models import RetrievedChunk


def clean_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def snippet_from_text(text: str, max_chars: int = 240) -> str:
    snippet = clean_whitespace(text)
    if len(snippet) <= max_chars:
        return snippet
    return snippet[: max_chars - 3].rstrip() + "..."


def chunk_to_citation(item: RetrievedChunk) -> CitationRecord:
    metadata = item.metadata
    return CitationRecord(
        citation=str(metadata.get("citation", item.chunk_id)),
        snippet=snippet_from_text(item.text),
        source_type=str(metadata.get("loai_van_ban", "")),
        legal_role=str(metadata.get("legal_role", "")),
        validity_status=str(metadata.get("validity_status", "")),
        source_verification_status=str(metadata.get("source_verification_status", "")),
        source_url=str(metadata.get("source_url") or metadata.get("url") or ""),
        source_file=str(metadata.get("source_file", "")),
        source_of_validity=str(metadata.get("source_of_validity", "")),
        validity_basis=str(metadata.get("validity_basis", "")),
        validity_confidence=str(metadata.get("validity_confidence", "")),
        relevance_score=round(float(item.scores.get("final", 0.0)), 3),
        relevance_label=item.relevance_label,
        relevance_rank=item.relevance_rank,
    )


def dedupe_citations(items: list[CitationRecord], limit: int | None = None) -> list[CitationRecord]:
    deduped: list[CitationRecord] = []
    seen: set[str] = set()
    for item in items:
        key = item.citation.strip().lower()
        if not key or key in seen:
            continue
        deduped.append(item)
        seen.add(key)
        if limit is not None and len(deduped) >= limit:
            break
    return deduped
