from ingestion.embedding.ollama_embedder import OllamaEmbedder
from retrieval.models import QueryIntent, RetrievedChunk
from retrieval.repository import QdrantRepository
from retrieval.retrievers.base import BaseRetriever
from qdrant_client import models


from app.config import settings

class VectorRetriever(BaseRetriever):
    name = "vector"

    def __init__(
        self,
        embed_model: str | None = None,
    ):
        model_to_use = embed_model or settings.embedding_model_name
        self.embedder = OllamaEmbedder(model_name=model_to_use)

    def retrieve(self, repository: QdrantRepository, query_intent: QueryIntent, limit: int = 20) -> list[RetrievedChunk]:
        query_text = " ; ".join(query_intent.query_variants) if query_intent.query_variants else query_intent.normalized_query
        vector = self.embedder.embed_text(query_text)
        if not vector:
            return []
            
        qdrant_filter = None
        if query_intent.loai_yeu_cau != "validity_question" and query_intent.loai_yeu_cau != "case_law_question":
            qdrant_filter = models.Filter(
                must_not=[
                    models.FieldCondition(
                        key="validity_status",
                        match=models.MatchValue(value="het_hieu_luc"),
                    )
                ]
            )

        response_points = repository.vector_search(vector=vector, limit=limit, query_filter=qdrant_filter)
        results = []
        for point in response_points:
            payload = point.payload or {}
            # Phase 3 Temporal/Graph filter for Vector Retriever
            if query_intent.time_context.get("year_hint"):
                year = query_intent.time_context["year_hint"]
                eff_to = payload.get("effective_to")
                if eff_to and len(eff_to) >= 4 and eff_to[:4] < year:
                    continue
                eff_from = payload.get("effective_from") or payload.get("ngay_hieu_luc")
                if eff_from and len(eff_from) >= 4 and eff_from[:4] > year:
                    continue

            results.append(
                RetrievedChunk(
                    chunk_id=str(payload.get("chunk_id", point.id)),
                    doc_id=str(payload.get("doc_id", "")),
                    text=payload.get("text", ""),
                    metadata={k: v for k, v in payload.items() if k not in {"chunk_id", "doc_id", "text"}},
                    scores={"vector": float(point.score or 0.0)},
                    sources=[self.name],
                )
            )
        return results
