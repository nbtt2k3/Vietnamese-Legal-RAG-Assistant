import re

from retrieval.models import QueryIntent, RetrievedChunk
from retrieval.repository import QdrantRepository
from retrieval.retrievers.base import BaseRetriever
from retrieval.text_utils import contains_normalized, normalize_for_match


class MetadataRetriever(BaseRetriever):
    name = "metadata"

    def retrieve(self, repository: QdrantRepository, query_intent: QueryIntent, limit: int = 20) -> list[RetrievedChunk]:
        results = []
        for payload in repository.all_payloads():
            score = self._score_payload(payload, query_intent)
            if score <= 0:
                continue
            results.append(
                RetrievedChunk(
                    chunk_id=str(payload.get("chunk_id", "")),
                    doc_id=str(payload.get("doc_id", "")),
                    text=payload.get("text", ""),
                    metadata={k: v for k, v in payload.items() if k not in {"chunk_id", "doc_id", "text"}},
                    scores={"metadata": score},
                    sources=[self.name],
                )
            )
        results.sort(key=lambda item: item.scores.get("metadata", 0.0), reverse=True)
        return results[:limit]

    def _score_payload(self, payload: dict, query_intent: QueryIntent) -> float:
        score = 0.0
        citation = str(payload.get("citation", ""))
        title = str(payload.get("ten", ""))
        dieu_title = str(payload.get("dieu_title", ""))
        chuong_title = str(payload.get("chuong_title", ""))
        normalized_dieu_title = normalize_for_match(dieu_title)
        source = payload.get("loai_van_ban")
        validity = str(payload.get("validity_status", "")).lower()

        if query_intent.loai_yeu_cau not in ("validity_question", "case_law_question") and validity == "het_hieu_luc":
            return 0.0

        if source in query_intent.source_priority:
            score += max(0.0, 2.5 - 0.35 * query_intent.source_priority.index(source))
        if source == "bo_luat":
            score += 0.8
        for target in query_intent.citation_targets:
            if contains_normalized(citation, target):
                score += 7.0
            if contains_normalized(title, target):
                score += 4.0
        for phrase in query_intent.key_phrases:
            if contains_normalized(dieu_title, phrase):
                score += 2.4
            if contains_normalized(chuong_title, phrase):
                score += 1.0
            if contains_normalized(title, phrase):
                score += 1.2
        if source in query_intent.source_preference:
            score += 2.5
        if payload.get("legal_role") in query_intent.legal_roles:
            score += 2.0
        if query_intent.time_context.get("year_hint"):
            year = query_intent.time_context["year_hint"]
            
            # Phase 3: Graph/Temporal filter
            eff_to = payload.get("effective_to")
            if eff_to and len(eff_to) >= 4 and eff_to[:4] < year:
                return 0.0
            eff_from = payload.get("effective_from") or payload.get("ngay_hieu_luc")
            if eff_from and len(eff_from) >= 4 and eff_from[:4] > year:
                return 0.0
                
            if year in str(payload.get("effective_date", "")) or year in str(payload.get("ngay_ban_hanh", "")):
                score += 2.0
        if query_intent.loai_yeu_cau == "scenario_application" and payload.get("document_role") == "case_law":
            score += 1.8
        if query_intent.loai_yeu_cau == "scenario_application" and source == "bo_luat":
            score += 1.0
        if query_intent.loai_yeu_cau == "validity_question" and "hieu luc" in normalized_dieu_title:
            score += 4.0
        if query_intent.loai_yeu_cau == "validity_question" and "the chap" in normalized_dieu_title and source == "bo_luat":
            score += 3.0
        if any(contains_normalized(phrase, "giao dịch dân sự vô hiệu do giả tạo") for phrase in query_intent.key_phrases) and "gia tao" in normalized_dieu_title:
            score += 5.0
        if any(contains_normalized(phrase, "giao dịch dân sự vô hiệu") for phrase in query_intent.key_phrases) and "vo hieu" in normalized_dieu_title and source == "bo_luat":
            score += 2.5
        if query_intent.loai_yeu_cau == "validity_question" and payload.get("transition_notes"):
            score += 1.2
        if payload.get("validity_status"):
            score += 0.2
        if re.search(r"Điều\s+\d+", str(payload.get("citation", "")), flags=re.IGNORECASE):
            score += 0.2
        return score
