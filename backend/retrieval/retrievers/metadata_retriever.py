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
        constraints = self._exact_constraints(query_intent)

        if query_intent.loai_yeu_cau not in ("validity_question", "case_law_question") and validity == "het_hieu_luc":
            return 0.0

        if constraints["doc_ids"] and payload.get("doc_id") not in constraints["doc_ids"]:
            return 0.0
        if constraints["doc_ids"] and payload.get("doc_id") in constraints["doc_ids"]:
            score += 10.0
        if constraints["source_types"] and source not in constraints["source_types"]:
            return 0.0
        if constraints["article_numbers"]:
            if str(payload.get("dieu_number", "")) in constraints["article_numbers"]:
                score += 25.0
            elif query_intent.loai_yeu_cau == "citation_lookup":
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
        if query_intent.time_context.get("year_hint") and query_intent.loai_yeu_cau != "citation_lookup":
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
        if query_intent.loai_yeu_cau == "validity_question" and "hieu luc thi hanh" in normalized_dieu_title:
            score += 6.0
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

    def _exact_constraints(self, query_intent: QueryIntent) -> dict[str, set[str]]:
        haystack = normalize_for_match(
            " ".join([query_intent.raw_query, query_intent.normalized_query, *query_intent.citation_targets])
        )
        article_numbers = set(re.findall(r"\bdieu\s+(\d+[a-z]?)\b", haystack))

        doc_ids: set[str] = set()
        source_types: set[str] = set()
        if "bo luat" in haystack or "luat" in haystack or (article_numbers and ("dan su" in haystack or "hinh su" in haystack)):
            source_types.add("bo_luat")
            if "dan su" in haystack:
                doc_ids.add("bo_luat_91_2015_QH13")
            if "hinh su" in haystack:
                doc_ids.add("bo_luat_100_2015_QH13")

        if "nghi dinh" in haystack:
            source_types.add("nghi_dinh")
            decree_match = re.search(r"\b(\d{1,4})\s*/\s*(\d{4})", haystack)
            if decree_match:
                number, year = decree_match.groups()
                doc_ids.add(f"nghi_dinh_{number}_{year}_ND_CP")

        if "nghi quyet" in haystack:
            source_types.add("nghi_quyet")
            resolution_match = re.search(r"\b(\d{1,3})\s*/\s*(\d{4})", haystack)
            if resolution_match:
                number, year = resolution_match.groups()
                doc_ids.add(f"nghi_quyet_{number.zfill(2)}_{year}_NQ_HDTP")

        return {
            "article_numbers": article_numbers,
            "doc_ids": doc_ids,
            "source_types": source_types,
        }
