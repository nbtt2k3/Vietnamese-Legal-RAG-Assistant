from rag.retrieval.models import QueryIntent, RetrievedChunk
from rag.retrieval.repository import QdrantRepository


class BaseRetriever:
    name = "base"

    def retrieve(
        self,
        repository: QdrantRepository,
        query_intent: QueryIntent,
        limit: int = 20,
    ) -> list[RetrievedChunk]:
        raise NotImplementedError
