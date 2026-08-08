from rag.retrieval.models import QueryIntent, RetrievedChunk
from rag.retrieval.repository import QdrantRepository
from qdrant_client.models import Filter, FieldCondition, MatchText
from rag.retrieval.text_utils import normalize_for_match


class CrossDocumentExpander:
    def expand(
        self,
        query_intent: QueryIntent,
        ranked: list[RetrievedChunk],
        repository: QdrantRepository,
        limit: int = 6,
    ) -> list[RetrievedChunk]:
        seeds = ranked[:8]
        target_terms = []
        for item in seeds:
            for rel in item.metadata.get("related_documents", []) or []:
                target = rel.get("target_doc")
                if target:
                    target_terms.append(str(target).lower())
            for ref in item.metadata.get("cited_authorities", []) or []:
                normalized_ref = ref.get("normalized_ref")
                if ref.get("ref_type") == "document" and normalized_ref:
                    target_terms.append(str(normalized_ref).lower())

        target_terms = list(dict.fromkeys(target_terms))
        if not target_terms:
            return []
            
        expansions: list[RetrievedChunk] = []
        seen_ids = {item.chunk_id for item in ranked}
        
        # Prefer the in-memory payload snapshot. It is deterministic and also
        # matches normalized Vietnamese names that Qdrant MatchText may miss.
        try:
            payloads = repository.all_payloads()
            for payload in payloads:
                haystack = normalize_for_match(" ".join(
                    str(payload.get(key, ""))
                    for key in ("citation", "so_hieu", "ten", "doc_id")
                ))
                matched_term = next((term for term in target_terms if normalize_for_match(term) in haystack), None)
                if not matched_term:
                    continue
                chunk_id = str(payload.get("chunk_id", ""))
                if not chunk_id or chunk_id in seen_ids:
                    continue
                score = 3.0 + (1.0 if payload.get("loai_van_ban") in query_intent.source_priority else 0.0)
                expansions.append(RetrievedChunk(
                    chunk_id=chunk_id,
                    doc_id=str(payload.get("doc_id", "")),
                    text=payload.get("text", ""),
                    metadata={k: v for k, v in payload.items() if k not in {"chunk_id", "doc_id", "text"}},
                    scores={"cross_ref": score},
                    sources=["cross_ref"],
                ))
                seen_ids.add(chunk_id)
                if len(expansions) >= limit:
                    return expansions
        except Exception:
            pass

        # Fallback for repositories that do not expose a payload snapshot.
        # Build should filters for each target term.
        should_conditions = []
        for term in target_terms:
            should_conditions.append(FieldCondition(key="citation", match=MatchText(text=term)))
            should_conditions.append(FieldCondition(key="ten", match=MatchText(text=term)))
            
        try:
            points, _ = repository.client.scroll(
                collection_name=repository.collection_name,
                scroll_filter=Filter(should=should_conditions),
                limit=limit * 3, # fetch extra to account for duplicates
                with_payload=True,
                with_vectors=False
            )
            
            for point in points:
                if len(expansions) >= limit:
                    break
                    
                payload = point.payload or {}
                chunk_id = str(payload.get("chunk_id", ""))
                if not chunk_id or chunk_id in seen_ids:
                    continue
                    
                score = 2.0
                if payload.get("loai_van_ban") in query_intent.source_priority:
                    score += max(0.0, 1.5 - 0.2 * query_intent.source_priority.index(payload.get("loai_van_ban")))
                    
                expansions.append(
                    RetrievedChunk(
                        chunk_id=chunk_id,
                        doc_id=str(payload.get("doc_id", "")),
                        text=payload.get("text", ""),
                        metadata={k: v for k, v in payload.items() if k not in {"chunk_id", "doc_id", "text"}},
                        scores={"cross_ref": score},
                        sources=["cross_ref"],
                    )
                )
                seen_ids.add(chunk_id)
                
        except Exception as e:
            from app.core.logging import logger
            logger.warning(f"Error during expander scroll: {e}")
            
        return expansions
