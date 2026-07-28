import time
from ingestion.source_registry import enrich_metadata_from_source_registry
from retrieval.constraints import exact_constraints, payload_matches_exact_constraints
from retrieval.evidence_builder import EvidenceBuilder
from retrieval.expander import CrossDocumentExpander
from retrieval.models import EvidenceBundle, QueryIntent, RetrievalResult, RetrievedChunk
from retrieval.query_analyzer import QueryAnalyzer
from retrieval.repository import QdrantRepository
from retrieval.reranker import LegalReranker
from retrieval.retrievers.lexical_retriever import LexicalRetriever
from retrieval.retrievers.metadata_retriever import MetadataRetriever
from retrieval.retrievers.vector_retriever import VectorRetriever


class RetrievalPipeline:
    def __init__(self):
        self.query_analyzer = QueryAnalyzer()
        self.retrievers = [
            MetadataRetriever(),
            LexicalRetriever(),
            VectorRetriever(),
        ]
        self.reranker = LegalReranker()
        self.evidence_builder = EvidenceBuilder()
        self.expander = CrossDocumentExpander()

    def run(self, query: str, candidate_limit: int = None, force_deterministic: bool = False, history: list = None) -> RetrievalResult:
        from app.config import settings
        candidate_limit = candidate_limit or settings.candidate_limit
        latency = {}
        
        t0 = time.time()
        query_intent = self.query_analyzer.analyze(query, force_deterministic=force_deterministic, history=history)
        latency["query_analyzer"] = round(time.time() - t0, 3)

        if query_intent.loai_yeu_cau == "out_of_scope":
            debug = {
                "retriever_hits": {},
                "merged_candidates": 0,
                "expanded_candidates": 0,
                "source_distribution": {},
                "latency": latency,
                "latency_total_retrieval": round(time.time() - t0, 3),
            }
            return RetrievalResult(
                query_intent=query_intent,
                candidates=[],
                evidence=EvidenceBundle(),
                confidence={
                    "level": "low",
                    "citation_match": False,
                    "multi_source_support": False,
                    "time_match": False,
                    "candidate_count": 0,
                },
                retrieval_debug=debug,
            )
        
        with QdrantRepository() as repository:
            t1 = time.time()
            merged, debug = self._collect_candidates(repository, query_intent)
            latency["retrievers"] = round(time.time() - t1, 3)
            
            # Giới hạn ứng viên để tránh cross-encoder bị timeout
            # Sort candidates by the new hybrid score
            candidates_list = list(merged.values())
            self._enrich_candidate_source_metadata(candidates_list)
            candidates_list.sort(key=lambda x: x.scores.get("hybrid", 0), reverse=True)
            candidates_list = candidates_list[:40]
            
            t2 = time.time()
            initial_ranked = self.reranker.rerank(query_intent, candidates_list, top_k=max(candidate_limit, 12))
            latency["reranker_initial"] = round(time.time() - t2, 3)
            
            t3 = time.time()
            expansions = self.expander.expand(query_intent, initial_ranked, repository)
            for item in expansions:
                # BUG-04 FIX: Gán hybrid score cho chunk mới từ expander.
                # Không có hybrid score → bị xếp hạng bằng 0 trong final rerank,
                # bất kể nội dung liên quan đến mức nào.
                if "hybrid" not in item.scores:
                    item.scores["hybrid"] = item.scores.get("cross_ref", 0.0)
                existing = merged.get(item.chunk_id)
                if existing:
                    existing.merge(item)
                else:
                    merged[item.chunk_id] = item
            latency["expander"] = round(time.time() - t3, 3)
            
            t4 = time.time()
            ranked = self.reranker.rerank(query_intent, list(merged.values()), top_k=candidate_limit)
            self._enrich_candidate_source_metadata(ranked)
            self._annotate_display_relevance(ranked)
            latency["reranker_final"] = round(time.time() - t4, 3)
            
            t5 = time.time()
            evidence = self.evidence_builder.build(query_intent, ranked)
            latency["evidence_builder"] = round(time.time() - t5, 3)
            
            confidence = self._build_confidence(query_intent, ranked, evidence)
            debug["expanded_candidates"] = len(expansions)
            debug["source_distribution"] = self._source_distribution(ranked)
            debug["latency"] = latency
            debug["latency_total_retrieval"] = round(time.time() - t0, 3)
            return RetrievalResult(
                query_intent=query_intent,
                candidates=ranked,
                evidence=evidence,
                confidence=confidence,
                retrieval_debug=debug,
            )

    def _collect_candidates(self, repository: QdrantRepository, query_intent: QueryIntent) -> tuple[dict[str, RetrievedChunk], dict[str, object]]:
        merged: dict[str, RetrievedChunk] = {}
        debug: dict[str, object] = {"retriever_hits": {}}
        
        # Phase 4 Query Routing
        active_retrievers = []
        if query_intent.loai_yeu_cau == "citation_lookup":
            active_retrievers = [r for r in self.retrievers if r.name in ("lexical", "metadata")]
        elif query_intent.loai_yeu_cau == "validity_question":
            active_retrievers = [r for r in self.retrievers if r.name in ("metadata", "lexical")]
        elif query_intent.loai_yeu_cau == "case_law_question":
            active_retrievers = [r for r in self.retrievers if r.name in ("vector", "lexical")]
        else: # scenario_application, conceptual_explanation, out_of_scope
            active_retrievers = self.retrievers
            
        for retriever in active_retrievers:
            items = retriever.retrieve(repository, query_intent, limit=32)
            debug["retriever_hits"][retriever.name] = len(items)
            for item in items:
                existing = merged.get(item.chunk_id)
                if existing:
                    existing.merge(item)
                else:
                    merged[item.chunk_id] = item

        if query_intent.loai_yeu_cau in {"citation_lookup", "validity_question"} and len(merged) < 8:
            vector_retriever = next((r for r in self.retrievers if r.name == "vector"), None)
            if vector_retriever and vector_retriever not in active_retrievers:
                items = vector_retriever.retrieve(repository, query_intent, limit=16)
                debug["retriever_hits"]["vector_fallback"] = len(items)
                for item in items:
                    existing = merged.get(item.chunk_id)
                    if existing:
                        existing.merge(item)
                    else:
                        merged[item.chunk_id] = item

        if query_intent.loai_yeu_cau in {"citation_lookup", "validity_question"}:
            merged = self._filter_exact_lookup_candidates(query_intent, merged, debug)
                    
        # Phase 4 Reciprocal Rank Fusion (RRF)
        if merged:
            k_rrf = 60
            rrf_sources = {"vector", "lexical", "metadata", "bm25"}

            # Chỉ reset hybrid=0 cho các chunk đã có ít nhất 1 điểm từ retriever thông thường.
            # Expander chunks (chỉ có "cross_ref") giữ nguyên hybrid score đã gán ở BUG-04 fix
            # để không bị underrank trong final rerank.
            for item in merged.values():
                if any(src in item.scores for src in rrf_sources):
                    item.scores["hybrid"] = 0.0

            for source in rrf_sources:
                # Sort items by score in descending order
                sorted_items = sorted(
                    [item for item in merged.values() if source in item.scores],
                    key=lambda x: x.scores[source],
                    reverse=True
                )
                # Assign RRF score based on rank (1-indexed)
                for rank, item in enumerate(sorted_items, start=1):
                    item.scores["hybrid"] += 1.0 / (k_rrf + rank)


        debug["merged_candidates"] = len(merged)
        return merged, debug

    def _enrich_candidate_source_metadata(self, items: list[RetrievedChunk]) -> None:
        for item in items:
            item.metadata = enrich_metadata_from_source_registry(item.metadata, doc_id=item.doc_id)

    def _filter_exact_lookup_candidates(
        self,
        query_intent: QueryIntent,
        merged: dict[str, RetrievedChunk],
        debug: dict[str, object],
    ) -> dict[str, RetrievedChunk]:
        constraints = exact_constraints(query_intent)
        if not any(constraints.values()):
            return merged

        filtered = {
            chunk_id: item
            for chunk_id, item in merged.items()
            if payload_matches_exact_constraints(
                {
                    **item.metadata,
                    "doc_id": item.doc_id,
                    "chunk_id": item.chunk_id,
                    "text": item.text,
                },
                constraints,
            )
        }
        if filtered:
            debug["exact_lookup_filtered_candidates"] = len(merged) - len(filtered)
            return filtered

        debug["exact_lookup_filtered_candidates"] = 0
        debug["exact_lookup_filter_skipped"] = True
        return merged

    def _build_confidence(
        self,
        query_intent: QueryIntent,
        ranked: list[RetrievedChunk],
        evidence,
    ) -> dict[str, object]:
        top = ranked[0] if ranked else None
        exact_citation = bool(
            top and query_intent.citation_targets and any(
                target.lower() in str(top.metadata.get("citation", "")).lower()
                for target in query_intent.citation_targets
            )
        )
        multi_source = len({item.metadata.get("loai_van_ban") for item in evidence.core_authorities if item.metadata.get("loai_van_ban")}) >= 2
        time_match = bool(
            top and query_intent.time_context.get("year_hint") and (
                query_intent.time_context["year_hint"] in str(top.metadata.get("effective_date", ""))
                or query_intent.time_context["year_hint"] in str(top.metadata.get("ngay_ban_hanh", ""))
            )
        )
        level = "low"
        if exact_citation or multi_source:
            level = "high"
        elif ranked:
            level = "medium"
        return {
            "level": level,
            "citation_match": exact_citation,
            "multi_source_support": multi_source,
            "time_match": time_match,
            "candidate_count": len(ranked),
        }

    def _source_distribution(self, ranked: list[RetrievedChunk]) -> dict[str, int]:
        result: dict[str, int] = {}
        for item in ranked:
            loai = str(item.metadata.get("loai_van_ban", "unknown"))
            result[loai] = result.get(loai, 0) + 1
        return result

    def _annotate_display_relevance(self, ranked: list[RetrievedChunk]) -> None:
        for index, item in enumerate(ranked, start=1):
            item.relevance_rank = index
            if index <= 3:
                item.relevance_label = "high"
            elif index <= 8:
                item.relevance_label = "medium"
            else:
                item.relevance_label = "low"
            self._ensure_numbered_citation(item)

    def _ensure_numbered_citation(self, item: RetrievedChunk) -> None:
        citation = str(item.metadata.get("citation", "")).strip()
        so_hieu = str(item.metadata.get("so_hieu", "")).strip()
        loai = str(item.metadata.get("loai_van_ban", "")).strip()
        if not citation or not so_hieu or so_hieu in citation:
            return
        display_names = {
            "nghi_dinh": "Nghị định",
            "nghi_quyet": "Nghị quyết",
            "thong_tu": "Thông tư",
        }
        prefix = display_names.get(loai)
        if prefix:
            item.metadata["citation"] = f"{prefix} {so_hieu} - {citation}"
