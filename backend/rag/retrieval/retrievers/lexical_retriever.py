import re

from rag.retrieval.models import QueryIntent, RetrievedChunk
from rag.retrieval.repository import QdrantRepository
from rag.retrieval.retrievers.base import BaseRetriever


import threading
from rank_bm25 import BM25Okapi
from rag.retrieval.text_utils import contains_normalized, normalize_for_match, tokenize_for_bm25
from rag.retrieval.temporal import allows_historical, temporal_state
from rag.retrieval.constraints import article_matches, exact_constraints

_GLOBAL_BM25_INDEX = None
_GLOBAL_PAYLOADS_LEN = 0
_GLOBAL_PAYLOADS = None
_BM25_LOCK = threading.Lock()


def clear_bm25_cache() -> None:
    """Invalidate the process-wide BM25 index after a collection rebuild."""
    global _GLOBAL_BM25_INDEX, _GLOBAL_PAYLOADS_LEN, _GLOBAL_PAYLOADS
    with _BM25_LOCK:
        _GLOBAL_BM25_INDEX = None
        _GLOBAL_PAYLOADS_LEN = 0
        _GLOBAL_PAYLOADS = None

class LexicalRetriever(BaseRetriever):
    name = "lexical"

    def _get_bm25_index(self, repository: QdrantRepository):
        global _GLOBAL_BM25_INDEX, _GLOBAL_PAYLOADS_LEN, _GLOBAL_PAYLOADS, _BM25_LOCK

        # BUG-02 FIX: Toàn bộ check + rebuild nằm trong critical section để tránh TOCTOU.
        # Trước đây current_count được đọc ngoài lock → hai thread có thể cùng thấy
        # index cần rebuild và double-rebuild, gây inconsistent state.
        with _BM25_LOCK:
            try:
                current_count = repository.client.count(collection_name=repository.collection_name, exact=True).count
            except Exception:
                current_count = -1

            if _GLOBAL_BM25_INDEX is None or _GLOBAL_PAYLOADS_LEN != current_count or _GLOBAL_PAYLOADS is None:
                _GLOBAL_PAYLOADS = repository.all_payloads()

                if not _GLOBAL_PAYLOADS:
                    _GLOBAL_BM25_INDEX = None
                    _GLOBAL_PAYLOADS_LEN = 0
                    return None, []

                tokenized_corpus = []
                for p in _GLOBAL_PAYLOADS:
                    text = p.get("text", "")
                    meta_text = " ".join(
                        str(p.get(key, ""))
                        for key in ("citation", "ten", "dieu_title", "chuong_title", "phan_loai")
                    )
                    tokenized_corpus.append(tokenize_for_bm25(f"{text} {meta_text}"))
                _GLOBAL_BM25_INDEX = BM25Okapi(tokenized_corpus)
                _GLOBAL_PAYLOADS_LEN = len(_GLOBAL_PAYLOADS)

            return _GLOBAL_BM25_INDEX, _GLOBAL_PAYLOADS

    def retrieve(self, repository: QdrantRepository, query_intent: QueryIntent, limit: int = 20) -> list[RetrievedChunk]:
        bm25, all_payloads = self._get_bm25_index(repository)
        if not all_payloads or bm25 is None:
            return []
            
        # Keep the complete query in BM25. Previously only extracted keywords
        # were indexed, which dropped important natural-language legal terms
        # and made unrelated high-frequency articles dominate the top ranks.
        query_text = " ".join(
            [query_intent.normalized_query, *query_intent.query_variants, *query_intent.keywords, *query_intent.key_phrases]
        ).lower()
        tokenized_query = tokenize_for_bm25(query_text)
        bm25_scores = bm25.get_scores(tokenized_query) if tokenized_query else [0]*len(all_payloads)

        results = []
        for idx, payload in enumerate(all_payloads):
            validity = str(payload.get("validity_status", "")).lower()
            if temporal_state(payload, query_intent) == "expired" and not allows_historical(query_intent):
                continue
                
            # Phase 3 Temporal/Graph filter
            if query_intent.time_context.get("year_hint"):
                year = query_intent.time_context["year_hint"]
                eff_to = payload.get("effective_to")
                if eff_to and len(eff_to) >= 4 and eff_to[:4] < year:
                    continue
                eff_from = payload.get("effective_from") or payload.get("ngay_hieu_luc")
                if eff_from and len(eff_from) >= 4 and eff_from[:4] > year:
                    continue
                
            text = payload.get("text", "")
            meta_text = " ".join(
                str(payload.get(key, ""))
                for key in ("citation", "ten", "dieu_title", "chuong_title", "phan_loai")
            )
            haystack = re.sub(r"\s+", " ", f"{text} {meta_text}".lower())
            
            # Phase 4 Hybrid score: BM25 + Rule-based heuristic
            bm25_score = bm25_scores[idx]
            rule_score = self._score_text(haystack, query_intent, payload)
            
            # Normalization (simple scaling)
            final_score = (bm25_score * 0.5) + rule_score
            if final_score <= 0:
                continue
                
            results.append(
                RetrievedChunk(
                    chunk_id=str(payload.get("chunk_id", "")),
                    doc_id=str(payload.get("doc_id", "")),
                    text=text,
                    metadata={k: v for k, v in payload.items() if k not in {"chunk_id", "doc_id", "text"}},
                    scores={"lexical": final_score, "bm25": bm25_score},
                    sources=[self.name],
                )
            )
        results.sort(key=lambda item: item.scores.get("lexical", 0.0), reverse=True)
        return results[:limit]

    def _score_text(self, haystack: str, query_intent: QueryIntent, payload: dict) -> float:
        score = 0.0
        normalized_haystack = normalize_for_match(haystack)
        for keyword in query_intent.keywords:
            if contains_normalized(normalized_haystack, keyword):
                score += 0.5
        for phrase in query_intent.key_phrases:
            if contains_normalized(normalized_haystack, phrase):
                score += 3.0
        for term in query_intent.scenario_terms:
            if contains_normalized(normalized_haystack, term):
                score += 1.2
        for target in query_intent.citation_targets:
            if contains_normalized(normalized_haystack, target):
                score += 6.0

        constraints = exact_constraints(query_intent)
        if constraints.get("clause_numbers"):
            clause_number = normalize_for_match(str(payload.get("khoan_number", "")))
            if clause_number in constraints["clause_numbers"] and article_matches(payload, constraints["article_numbers"]):
                score += 12.0

        dieu_title = normalize_for_match(str(payload.get("dieu_title", "")))
        citation = normalize_for_match(str(payload.get("citation", "")))
        normalized_query = normalize_for_match(query_intent.normalized_query)
        if query_intent.loai_yeu_cau == "validity_question" and "hieu luc" in dieu_title:
            score += 4.0
        if query_intent.loai_yeu_cau == "validity_question" and "the chap" in dieu_title and payload.get("loai_van_ban") == "bo_luat":
            score += 3.0
        if query_intent.loai_yeu_cau == "scenario_application" and payload.get("document_role") == "case_law":
            score += 2.0
        if query_intent.loai_yeu_cau == "scenario_application" and payload.get("loai_van_ban") == "bo_luat":
            score += 0.8
        if any(contains_normalized(phrase, "giao dịch dân sự vô hiệu do giả tạo") for phrase in query_intent.key_phrases) and "gia tao" in normalized_haystack:
            score += 5.0
        if citation.startswith("an le so") and "an le" in normalized_query:
            score += 2.0
        return score
