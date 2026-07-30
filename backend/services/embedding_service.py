from sentence_transformers import SentenceTransformer

# Using bge-small-en-v1.5 locally downloaded
EMBEDDING_MODEL_NAME = "/Users/abhinavkumarsingh/ENO/bge_model"

class EmbeddingService:
    def __init__(self, model_name: str = EMBEDDING_MODEL_NAME):
        print(f"Loading Embedding model: {model_name}")
        self.model = SentenceTransformer(model_name)

    def embed_text(self, text: str) -> list[float]:
        # Generate embeddings
        embedding = self.model.encode(text, normalize_embeddings=True)
        return embedding.tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        embeddings = self.model.encode(texts, normalize_embeddings=True)
        return embeddings.tolist()

embedding_service = EmbeddingService()
