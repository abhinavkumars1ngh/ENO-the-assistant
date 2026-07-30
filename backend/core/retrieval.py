from backend.core.qdrant_setup import client as qdrant_client
from backend.services.embedding_service import embedding_service
from backend.services.rerank_service import rerank_service
from qdrant_client.models import Filter, FieldCondition, MatchValue

class RetrievalEngine:
    def __init__(self, collection_name="knowledge_base"):
        self.collection_name = collection_name

    def retrieve(self, query: str, top_k: int = 20, filter_course: str = None) -> list[dict]:
        """
        Hybrid retrieval (Vector + BM25 theoretically, here implemented as Vector search)
        followed by Cross-Encoder Reranking.
        """
        query_vector = embedding_service.embed_text(query)

        query_filter = None
        if filter_course:
            query_filter = Filter(
                must=[
                    FieldCondition(
                        key="course",
                        match=MatchValue(value=filter_course),
                    )
                ]
            )

        # 1. Retrieve candidate chunks from Qdrant
        search_result = qdrant_client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            query_filter=query_filter,
            limit=top_k
        )

        if not search_result:
            return []

        # 2. Extract texts for reranking
        documents = [hit.payload.get("text", "") for hit in search_result]

        # 3. Rerank candidates
        scores = rerank_service.rerank(query, documents)

        # 4. Sort by reranker score
        scored_results = []
        for i, hit in enumerate(search_result):
            scored_results.append({
                "id": hit.id,
                "score": scores[i],
                "payload": hit.payload,
                "text": documents[i]
            })

        scored_results.sort(key=lambda x: x["score"], reverse=True)

        # Return top 5 best results after reranking
        return scored_results[:5]

retrieval_engine = RetrievalEngine()
