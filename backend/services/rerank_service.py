from sentence_transformers import CrossEncoder

RERANK_MODEL_NAME = "/Users/abhinavkumarsingh/ENO/reranker_model"

class RerankService:
    def __init__(self, model_name: str = RERANK_MODEL_NAME):
        print(f"Loading Reranker model: {model_name}")
        self.model = CrossEncoder(model_name)

    def rerank(self, query: str, documents: list[str]) -> list[float]:
        # Returns a list of relevance scores
        pairs = [[query, doc] for doc in documents]
        scores = self.model.predict(pairs)
        return scores.tolist()

rerank_service = RerankService()
