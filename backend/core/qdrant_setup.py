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

# Initialize Qdrant Client (Dynamic switch)
if is_qdrant_running():
    print("[Eno AI] Qdrant detected on port 6333. Connecting to Docker instance.")
    client = QdrantClient(url="http://127.0.0.1:6333")
else:
    print("[Eno AI] Qdrant not found on port 6333. Falling back to local disk storage.")
    client = QdrantClient(path=QDRANT_PATH)

def init_qdrant():
    collections = [c.name for c in client.get_collections().collections]
    
    # 384 dimensions for bge-small-en-v1.5
    if "knowledge_base" not in collections:
        client.create_collection(
            collection_name="knowledge_base",
            vectors_config=VectorParams(size=384, distance=Distance.COSINE),
        )
        print("Created collection 'knowledge_base' in Qdrant.")
