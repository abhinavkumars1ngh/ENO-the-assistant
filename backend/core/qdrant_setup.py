"""
Qdrant Embedded Local Vector Store Setup

Runs 100% in-process and serverless via Qdrant's embedded SQLite/mmap backend.
No Docker, no virtual machines, and no external background daemon.

IMPORTANT ARCHITECTURAL CONSTRAINT:
Qdrant's embedded local mode uses portalocker for an exclusive OS-level file lock
on the storage directory. Only the main backend process may open this storage path
at a time. This is a real structural constraint of embedded mode, NOT a bug.
Any test or standalone utility script needing a separate vector store must pass
its own isolated storage directory (e.g. storage/qdrant_test or ':memory:'),
never the live path.
"""
from pathlib import Path
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from backend.core import config

QDRANT_LOCAL_PATH = str(config.PROJECT_ROOT / "storage" / "qdrant_local")

# Single in-process embedded Qdrant client instance
client = QdrantClient(path=QDRANT_LOCAL_PATH)

def init_qdrant():
    """Ensure the knowledge_base collection exists in the local embedded index."""
    collections = [c.name for c in client.get_collections().collections]
    
    # 384 dimensions for bge-small-en-v1.5
    if "knowledge_base" not in collections:
        client.create_collection(
            collection_name="knowledge_base",
            vectors_config=VectorParams(size=384, distance=Distance.COSINE),
        )
        print(f"[Eno RAG] Initialized 'knowledge_base' collection in {QDRANT_LOCAL_PATH}.")
