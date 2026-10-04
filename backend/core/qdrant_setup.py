from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
import os
import socket

QDRANT_PATH = "/Users/abhinavkumarsingh/ENO/storage/qdrant"

def is_qdrant_running(host="127.0.0.1", port=6333, timeout=0.5):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False

_client = None

def get_qdrant_client() -> QdrantClient:
    global _client
    if _client is not None:
        return _client

    if is_qdrant_running():
        print("[Eno AI] Qdrant detected on port 6333. Connecting to Docker instance.")
        _client = QdrantClient(url="http://127.0.0.1:6333")
        return _client

    print("[Eno AI] Qdrant not found on port 6333. Falling back to local disk storage.")
    try:
        _client = QdrantClient(path=QDRANT_PATH)
        return _client
    except Exception as e:
        print(f"[Eno AI] Notice: Local Qdrant folder locked by another process ({type(e).__name__}). Using in-memory fallback to enable concurrent operation without crashing.")
        _client = QdrantClient(":memory:")
        return _client

client = get_qdrant_client()

def init_qdrant():
    cl = get_qdrant_client()
    try:
        collections = [c.name for c in cl.get_collections().collections]
        
        # 384 dimensions for bge-small-en-v1.5
        if "knowledge_base" not in collections:
            cl.create_collection(
                collection_name="knowledge_base",
                vectors_config=VectorParams(size=384, distance=Distance.COSINE),
            )
            print("Created collection 'knowledge_base' in Qdrant.")
    except Exception as e:
        print(f"[Eno AI] Non-fatal Qdrant init notice: {e}")
